
function [isValid, message, metadata] = validateModelMetadata(modelDir)
% VALIDATEMODELMETADATA Check saved metadata and checkpoint presence.
% This is a preliminary check, not proof of model correctness.

isValid = false;
message = '';
metadata = struct();

metadataPath = fullfile(modelDir, 'model_metadata.mat');

if ~isfolder(modelDir)
    message = 'Model directory does not exist.';
    return;
end

if ~isfile(metadataPath)
    message = 'Model metadata file has not been created.';
    return;
end

try
    loaded = load(metadataPath, 'metadata');
catch ME
    message = ['Could not read metadata: ', ME.message];
    return;
end

if ~isfield(loaded, 'metadata') || ~isstruct(loaded.metadata)
    message = 'Metadata file has an invalid structure.';
    return;
end

metadata = loaded.metadata;

required = {'architecture', 'dataset', 'inputSize', ...
    'classOrder', 'preprocessing', 'modelFile'};

for k = 1:numel(required)
    if ~isfield(metadata, required{k})
        message = ['Metadata is missing field: ', required{k}];
        return;
    end
end

if ~isequal(metadata.classOrder, 0:4)
    message = 'Metadata class order does not match grades 0–4.';
    return;
end

if isempty(metadata.modelFile)
    message = 'Model filename is empty.';
    return;
end

modelPath = fullfile(modelDir, metadata.modelFile);

if ~isfile(modelPath)
    message = 'The configured model checkpoint does not exist.';
    return;
end

isValid = true;
message = ...
    'Metadata and checkpoint presence checks passed; model loading remains unverified.';
end
