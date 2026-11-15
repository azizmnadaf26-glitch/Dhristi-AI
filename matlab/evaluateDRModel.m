
function metrics = evaluateDRModel(trueLabels, predictedLabels)
% EVALUATEDRMODEL Evaluate five-grade DR classification.
% Labels must be integer grades 0, 1, 2, 3, or 4.
% Rows represent true grades; columns represent predicted grades.

validateattributes(trueLabels, {'numeric'}, ...
    {'real', 'finite', 'vector', 'nonempty'});
validateattributes(predictedLabels, {'numeric'}, ...
    {'real', 'finite', 'vector', 'nonempty'});

yTrue = double(trueLabels(:));
yPred = double(predictedLabels(:));

if numel(yTrue) ~= numel(yPred)
    error('RetinaGuide:LabelCountMismatch', ...
        'True and predicted labels must have equal lengths.');
end

if any(~ismember(yTrue, 0:4)) || any(~ismember(yPred, 0:4))
    error('RetinaGuide:InvalidGrade', ...
        'All labels must be integer grades from 0 to 4.');
end

% Fixed 5-by-5 confusion matrix.
C = zeros(5, 5);

for k = 1:numel(yTrue)
    C(yTrue(k)+1, yPred(k)+1) = ...
        C(yTrue(k)+1, yPred(k)+1) + 1;
end

tp = diag(C);
support = sum(C, 2);
predictedCount = sum(C, 1)';

precision = zeros(5, 1);
recall = zeros(5, 1);
f1 = zeros(5, 1);

hasPredictions = predictedCount > 0;
hasTrueSamples = support > 0;

precision(hasPredictions) = ...
    tp(hasPredictions) ./ predictedCount(hasPredictions);

recall(hasTrueSamples) = ...
    tp(hasTrueSamples) ./ support(hasTrueSamples);

validF1 = precision + recall > 0;
f1(validF1) = ...
    2 .* precision(validF1) .* recall(validF1) ./ ...
    (precision(validF1) + recall(validF1));

% Macro metrics across all five grades.
macroPrecision = mean(precision);
macroRecall = mean(recall);
macroF1 = mean(f1);

% Overall accuracy.
accuracy = sum(tp) / numel(yTrue);

% Quadratic weighted kappa.
N = sum(C, 'all');
observedAgreement = C / N;
expected = (support * predictedCount') / (N^2);

[trueGrid, predGrid] = ndgrid(0:4, 0:4);
weights = ((trueGrid - predGrid).^2) / 16;

observedDisagreement = sum(weights .* observedAgreement, 'all');
expectedDisagreement = sum(weights .* expected, 'all');

if expectedDisagreement > 0
    qwk = 1 - observedDisagreement / expectedDisagreement;
else
    qwk = NaN;
end

metrics.confusionMatrix = C;
metrics.accuracy = accuracy;
metrics.perClassPrecision = precision;
metrics.perClassRecall = recall;
metrics.perClassF1 = f1;
metrics.macroPrecision = macroPrecision;
metrics.macroRecall = macroRecall;
metrics.macroF1 = macroF1;
metrics.quadraticWeightedKappa = qwk;
metrics.gradeLabels = {'0', '1', '2', '3', '4'};
metrics.sampleCount = numel(yTrue);
end
