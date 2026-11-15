
function results = validateRetinaGuide(net, validationDir)

% Full Fold 2 validation evaluation
manifestPath = fullfile(validationDir, ...
    'fold2_validation_manifest.csv');

if ~isfile(manifestPath)
    error('RetinaGuide:ManifestMissing', ...
        'Validation manifest not found: %s', manifestPath);
end

manifest = readtable(manifestPath);
numImages = height(manifest);

if numImages == 0
    error('RetinaGuide:EmptyManifest', ...
        'The validation manifest contains no records.');
end

% Verify all image files before inference
for i = 1:numImages
    imagePath = fullfile(validationDir, ...
        char(manifest.filename{i}));

    if ~isfile(imagePath)
        error('RetinaGuide:ImageMissing', ...
            'Image missing: %s', imagePath);
    end
end

% Initialize result arrays
trueGrades = double(manifest.ground_truth_grade);
predictedGrades = -ones(numImages, 1);
confidences = nan(numImages, 1);
predictedLabels = strings(numImages, 1);
statuses = strings(numImages, 1);
errorMessages = strings(numImages, 1);

% Five output probability columns, grades 0 to 4
probabilities = nan(numImages, 5);

fprintf('\nRETINAGUIDE FULL FOLD 2 VALIDATION\n');
fprintf('Total images: %d\n\n', numImages);

for i = 1:numImages

    imagePath = fullfile(validationDir, ...
        char(manifest.filename{i}));

    try
        img = imread(imagePath);

        prediction = runRetinaInference(net, img);

        if numel(prediction.probabilities) ~= 5
            error('Expected five class probabilities.');
        end

        predictedGrades(i) = prediction.predictedGrade;
        confidences(i) = prediction.confidence;
        predictedLabels(i) = string(prediction.predictedClass);

        probabilities(i, :) = ...
            reshape(prediction.probabilities, 1, 5);

        statuses(i) = "Success";
        errorMessages(i) = "";

        fprintf('%3d/%3d | True: %d | Predicted: %d | Confidence: %.2f%%\n', ...
            i, numImages, trueGrades(i), ...
            predictedGrades(i), confidences(i)*100);

    catch ME

        predictedLabels(i) = "Inference Failed";
        statuses(i) = "Failed";
        errorMessages(i) = string(ME.message);

        fprintf('%3d/%3d | Failed: %s\n', ...
            i, numImages, ME.message);

    end
end

% Create results table
results = table( ...
    string(manifest.filename), ...
    trueGrades, ...
    predictedGrades, ...
    predictedLabels, ...
    confidences, ...
    probabilities(:,1), ...
    probabilities(:,2), ...
    probabilities(:,3), ...
    probabilities(:,4), ...
    probabilities(:,5), ...
    statuses, ...
    errorMessages, ...
    'VariableNames', { ...
    'filename', 'trueGrade', 'predictedGrade', ...
    'predictedClass', 'confidence', ...
    'prob_NoDR', 'prob_Mild', 'prob_Moderate', ...
    'prob_Severe', 'prob_Proliferative', ...
    'status', 'errorMessage'});

% Calculate accuracy on successful inferences
successful = statuses == "Success";

fprintf('\nSuccessful inferences: %d/%d\n', ...
    sum(successful), numImages);

fprintf('Failed inferences: %d/%d\n', ...
    sum(~successful), numImages);

if any(successful)

    accuracy = mean( ...
        trueGrades(successful) == ...
        predictedGrades(successful)) * 100;

    fprintf('Accuracy on successful inferences: %.2f%%\n', ...
        accuracy);

else
    fprintf('\nNo successful predictions.\n');
end

% Save separate full-validation results
outputPath = fullfile(validationDir, ...
    'retinaguide_full_fold2_validation_results.csv');

writetable(results, outputPath);

fprintf('\nFull validation results saved to:\n%s\n', ...
    outputPath);

end
