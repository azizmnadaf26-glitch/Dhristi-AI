
function displayData = formatDRResults(result)
% FORMATDRRESULTS Prepare validated prediction data for the UI.

requiredFields = {'grade', 'label', 'confidence', 'probabilities'};

for k = 1:numel(requiredFields)
    if ~isfield(result, requiredFields{k})
        error('RetinaGuide:MissingResultField', ...
            'Prediction result is missing field: %s', ...
            requiredFields{k});
    end
end

% Validate the grade and confidence.
validateattributes(result.grade, {'numeric'}, ...
    {'real', 'finite', 'scalar', 'integer', '>=', 0, '<=', 4});

validateattributes(result.confidence, {'numeric'}, ...
    {'real', 'finite', 'scalar', '>=', 0, '<=', 1});

probabilities = double(result.probabilities(:)');

if numel(probabilities) ~= 5 || ...
        any(~isfinite(probabilities)) || ...
        any(probabilities < 0) || any(probabilities > 1) || ...
        abs(sum(probabilities) - 1) > 1e-3
    error('RetinaGuide:InvalidProbabilities', ...
        'Expected five valid probabilities that sum to 1.');
end

if abs(max(probabilities) - result.confidence) > 1e-3
    error('RetinaGuide:ConfidenceMismatch', ...
        'Confidence must match the highest class probability.');
end

displayData.gradeText = sprintf('DR Grade: %d', result.grade);
displayData.labelText = char(result.label);
displayData.confidenceText = sprintf( ...
    'Model probability: %.1f%%', result.confidence * 100);

displayData.probabilityText = cell(5, 1);

for k = 1:5
    displayData.probabilityText{k} = sprintf( ...
        'Grade %d: %.1f%%', k-1, probabilities(k)*100);
end

displayData.statusText = 'Prediction result formatted';
displayData.disclaimer = ...
    'Research prototype output; not a clinical diagnosis.';
end
