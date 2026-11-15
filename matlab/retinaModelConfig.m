function config = retinaModelConfig()
% RETINAMODELCONFIG
% Deployment configuration for RetinaGuide XAI.
% Uses the verified Fold 2 EfficientNet-B0 legacy ONNX model.

projectDir = 'C:\\Users\\azizn\\RetinaGuideXAI\\matlab';

config.dataset = 'APTOS 2019 Blindness Detection';
config.architecture = 'EfficientNet-B0';

% Class indices: 0, 1, 2, 3, 4
config.grades = 0:4;

config.gradeLabels = {
    'No DR'
    'Mild DR'
    'Moderate DR'
    'Severe DR'
    'Proliferative DR'
    };

% Verified training input dimensions
config.inputSize = [384 384];
config.inputChannels = 3;

% RGB input, PIL bilinear resize, ToTensor,
% ImageNet mean/std normalization, NCHW in Python.
config.preprocessingConfirmed = true;
config.classOrderConfirmed = true;

% Deployment model
config.modelFile = fullfile( ...
    projectDir, ...
    'deployment_package', ...
    'retinaguide_efficientnet_b0_legacy.onnx');

config.modelAvailable = isfile(config.modelFile);

% Retinal Image Authenticity Filter Configuration (Tier A & Tier B)
config.enableAuthenticityFilter = true;
config.maxCornerBrightness = 0.12;
config.minRedToGreenRatio = 0.95;
config.minRedToBlueRatio = 1.00;

% Fitted Post-Hoc Temperature Calibration (Fitted on 299 calibration samples)
config.temperature = 2.7600;

config.status = ...
    'Fold 2 deployment model configured with 2-tier authenticity filter and temperature calibration T=2.76.';

end
