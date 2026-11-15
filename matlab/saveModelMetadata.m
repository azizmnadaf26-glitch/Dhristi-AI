
function metadata = saveModelMetadata(modelDir, trainingInfo)
% SAVEMODELMETADATA Validate and save verified model metadata.
% Supply trainingInfo only after checking the actual training pipeline.
% This function does not save model weights or validate model accuracy.

required = {'architecture', 'dataset', 'inputSize', ...
    'classOrder', 'preprocessing', 'modelFile'};

for k = 1:numel(required)
    if ~isfield(trainingInfo, required{k})
        error('RetinaGuide:MissingMetadata', ...
            'Missing metadata field: %s', required{k});
    end
end

if ~isfolder(modelDir)
    error('RetinaGuide:MissingModelDirectory', ...
        'The model directory does not exist.');
end

if ~isequal(trainingInfo.classOrder, 0:4)
    error('RetinaGuide:InvalidClassOrder', ...
        'Class order must be [0 1 2 3 4].');
end

validateattributes(trainingInfo.inputSize, {'numeric'}, ...
    {'real', 'finite', 'vector', 'numel', 2, 'positive', 'integer'});

if isempty(trainingInfo.preprocessing) || ...
        isempty(trainingInfo.modelFile)
    error('RetinaGuide:IncompleteMetadata', ...
        'Preprocessing and model filename must be specified.');
end

metadata = trainingInfo;
metadata.metadataVersion = 1;
metadata.savedAt = char(datetime('now', ...
    'Format', 'yyyy-MM-dd HH:mm:ss'));
metadata.verificationStatus = ...
    'Metadata supplied; model validity not independently verified';

metadataPath = fullfile(modelDir, 'model_metadata.mat');
save(metadataPath, 'metadata');

fprintf('Metadata saved to:\n%s\n', metadataPath);
end
