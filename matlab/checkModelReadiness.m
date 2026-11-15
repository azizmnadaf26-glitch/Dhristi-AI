
function status = checkModelReadiness(config)
% CHECKMODELREADINESS Check whether model integration is configured.
% This checks configuration and file presence, not model validity.

status.ready = false;
status.message = '';
status.modelPath = '';

requiredFields = {'modelFile', 'modelAvailable', ...
    'preprocessingConfirmed', 'classOrderConfirmed'};

for k = 1:numel(requiredFields)
    if ~isfield(config, requiredFields{k})
        status.message = ['Missing configuration field: ', ...
            requiredFields{k}];
        return;
    end
end

if isempty(config.modelFile)
    status.message = 'Model file path has not been configured.';
    return;
end

if ~isfile(config.modelFile)
    status.message = 'Configured model file does not exist.';
    return;
end

if ~config.modelAvailable
    status.message = 'Model has not been marked as available.';
    return;
end

if ~config.preprocessingConfirmed
    status.message = 'Model preprocessing has not been verified.';
    return;
end

if ~config.classOrderConfirmed
    status.message = 'Model class order has not been verified.';
    return;
end

status.ready = true;
status.message = 'Configuration checks passed; validate model loading before inference.';
status.modelPath = config.modelFile;
end
