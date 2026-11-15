function results = evaluateModelReproducible()
% EVALUATEMODELREPRODUCIBLE
% Comprehensive, reproducible evaluation harness for RetinaGuide XAI.
% Evaluates the active ONNX EfficientNet-B0 model on the Fold-2 validation set.
% Computes:
%   - 5x5 Confusion Matrix
%   - Accuracy, Balanced Accuracy
%   - Macro and Weighted Precision, Recall, F1
%   - Quadratic Weighted Kappa (QWK)
%   - Binary Referable DR Sensitivity, Specificity, FNR
%   - Expected Calibration Error (ECE), MCE, Brier Score

cfg = retinaModelConfig();
fprintf('\n======================================================\n');
fprintf('RETINAGUIDE XAI - REPRODUCIBLE MODEL EVALUATION\n');
fprintf('======================================================\n');
fprintf('Architecture:  %s\n', cfg.architecture);
fprintf('Model File:    %s\n', cfg.modelFile);

if ~isfile(cfg.modelFile)
    error('RetinaGuide:ModelMissing', 'Model file not found: %s', cfg.modelFile);
end

% Compute model SHA-256
net = importNetworkFromONNX(cfg.modelFile);
fprintf('Network successfully imported. Total layers: %d\n', numel(net.Layers));

valDir = fullfile('C:\Users\azizn\RetinaGuideXAI\matlab', 'full_validation_images');
manifestPath = fullfile(valDir, 'fold2_validation_manifest.csv');
if ~isfile(manifestPath)
    error('RetinaGuide:ManifestMissing', 'Manifest missing: %s', manifestPath);
end

manifest = readtable(manifestPath);
N = height(manifest);
fprintf('Total Manifest Samples: %d\n', N);

% Run inference across all images
trueGrades = double(manifest.ground_truth_grade);
predGrades = zeros(N, 1);
confidences = zeros(N, 1);
probs = zeros(N, 5);

for i = 1:N
    imgPath = fullfile(valDir, manifest.filename{i});
    img = imread(imgPath);
    pred = runRetinaInference(net, img);
    predGrades(i) = pred.predictedGrade;
    confidences(i) = pred.confidence;
    probs(i, :) = reshape(pred.probabilities, 1, 5);
end

% 1. Confusion Matrix
C = zeros(5, 5);
for i = 1:N
    C(trueGrades(i)+1, predGrades(i)+1) = C(trueGrades(i)+1, predGrades(i)+1) + 1;
end

support = sum(C, 2);
predCount = sum(C, 1)';
tp = diag(C);

precision = tp ./ max(predCount, 1);
recall = tp ./ max(support, 1);
f1 = 2 .* precision .* recall ./ max(precision + recall, 1e-9);

acc = sum(tp) / N;
macroP = mean(precision);
macroR = mean(recall);
macroF1 = mean(f1);
weightedF1 = sum(f1 .* support) / N;
balancedAcc = macroR;

% 2. Quadratic Weighted Kappa
[tGrid, pGrid] = ndgrid(0:4, 0:4);
weights = ((tGrid - pGrid).^2) / 16;
obsDist = sum(weights .* (C / N), 'all');
expDist = sum(weights .* ((support * predCount') / (N^2)), 'all');
qwk = 1 - obsDist / expDist;

% 3. Referable DR (Grade >= 2)
refTrue = trueGrades >= 2;
refPred = predGrades >= 2;
tpRef = sum(refTrue & refPred);
fpRef = sum(~refTrue & refPred);
fnRef = sum(refTrue & ~refPred);
tnRef = sum(~refTrue & ~refPred);

sens = tpRef / max(tpRef + fnRef, 1);
spec = tnRef / max(tnRef + fpRef, 1);
fnr  = fnRef / max(tpRef + fnRef, 1);

% 4. Calibration Metrics
brier = 0;
for i = 1:N
    oneHot = zeros(1, 5);
    oneHot(trueGrades(i)+1) = 1.0;
    brier = brier + sum((probs(i,:) - oneHot).^2);
end
brier = brier / N;

% 10-bin ECE
ece = 0;
mce = 0;
for b = 0:9
    low = b / 10;
    high = (b + 1) / 10;
    inBin = (confidences >= low) & (confidences < high);
    if b == 9, inBin = inBin | (confidences == 1.0); end
    if any(inBin)
        avgConf = mean(confidences(inBin));
        binAcc = mean(trueGrades(inBin) == predGrades(inBin));
        gap = abs(binAcc - avgConf);
        ece = ece + (sum(inBin) / N) * gap;
        if gap > mce, mce = gap; end
    end
end

% Print Results
fprintf('\n--- EVALUATION SUMMARY ---\n');
fprintf('Overall Accuracy:       %.2f%%\n', acc * 100);
fprintf('Balanced Accuracy:      %.2f%%\n', balancedAcc * 100);
fprintf('Macro Precision:        %.4f\n', macroP);
fprintf('Macro Recall:           %.4f\n', macroR);
fprintf('Macro F1-Score:         %.4f\n', macroF1);
fprintf('Weighted F1-Score:      %.4f\n', weightedF1);
fprintf('Quadratic W. Kappa:     %.4f\n', qwk);
fprintf('\n--- REFERABLE DR SCREENING (Threshold Grade >= 2) ---\n');
fprintf('Sensitivity (Recall):   %.2f%%\n', sens * 100);
fprintf('Specificity:            %.2f%%\n', spec * 100);
fprintf('False Negative Rate:    %.2f%%\n', fnr * 100);
fprintf('\n--- CALIBRATION METRICS ---\n');
fprintf('Expected Calib. Error:  %.2f%%\n', ece * 100);
fprintf('Max Calib. Error:       %.2f%%\n', mce * 100);
fprintf('Brier Score:            %.4f\n', brier);

results.confusionMatrix = C;
results.accuracy = acc;
results.macroF1 = macroF1;
results.weightedF1 = weightedF1;
results.quadraticWeightedKappa = qwk;
results.referableSensitivity = sens;
results.referableSpecificity = spec;
results.referableFNR = fnr;
results.ece = ece;
results.mce = mce;
results.brier = brier;

end
