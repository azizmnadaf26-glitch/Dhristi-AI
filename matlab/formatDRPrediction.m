
function result = formatDRPrediction(probabilities)
% FORMATDRPREDICTION Format five-class DR model probabilities.
% Class order must be [0 1 2 3 4].
% This function formats model output; it does not diagnose disease.

validateattributes(probabilities, {'numeric'}, ...
    {'real', 'finite', 'vector', 'numel', 5}, ...
    mfilename, 'probabilities');

probabilities = double(probabilities(:)');

if any(probabilities < 0) || any(probabilities > 1)
    error('RetinaGuide:InvalidProbabilities', ...
        'Probabilities must be between 0 and 1.');
end

if abs(sum(probabilities) - 1) > 1e-3
    error('RetinaGuide:InvalidProbabilities', ...
        'Probabilities must sum to approximately 1.');
end

% APTOS 2019 grade labels, ordered from 0 to 4.
gradeNames = {
    'No DR'
    'Mild DR'
    'Moderate DR'
    'Severe DR'
    'Proliferative DR'
    };

[confidence, classIndex] = max(probabilities);
predictedGrade = classIndex - 1;

result.grade = predictedGrade;
result.label = gradeNames{classIndex};
result.confidence = confidence;
result.probabilities = probabilities;
result.gradeNames = gradeNames;
result.status = 'Prediction formatted successfully';
result.disclaimer = ...
    'Research prototype output; not a clinical diagnosis.';
end
