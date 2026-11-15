function result = checkImageQuality(img)
% CHECKIMAGEQUALITY
% Two-tier technical quality and retinal authenticity check for fundus images.
%
% Input:
%   img    - RGB or grayscale image loaded into MATLAB
%
% Output:
%   result - structure containing measurements, status, and reasons
%
% NOTE: Thresholds are engineering heuristics for technical quality and
% domain screening, not clinically validated diagnostic criteria.

% Initialize output
result = struct();
result.isUsable = false;
result.status = "Review required";
result.reasons = strings(0,1);

% Check that the input exists and is a valid image array
if isempty(img) || (~isnumeric(img) && ~islogical(img))
    result.reasons = "Input is empty or is not a numeric image array.";
    return;
end

if ndims(img) > 3 || (ndims(img) == 3 && size(img,3) ~= 3)
    result.reasons = "Unsupported image dimensions or channel count.";
    return;
end

% Convert to floating-point values in the range [0,1]
img = im2double(img);

% Convert RGB to grayscale when necessary
if ndims(img) == 3
    gray = rgb2gray(img);
else
    gray = img;
end

% 1. Image dimensions
result.height = size(gray,1);
result.width = size(gray,2);
result.dimensionsPass = ...
    result.height >= 224 && result.width >= 224;

% 2. Brightness
result.meanBrightness = mean(gray(:));
result.brightnessPass = ...
    result.meanBrightness >= 0.10 && ...
    result.meanBrightness <= 0.90;

% 3. Contrast
result.contrastStd = std(gray(:));
result.contrastPass = result.contrastStd >= 0.05;

% 4. Preliminary sharpness estimate using image gradients
[Gx, Gy] = imgradientxy(gray);
gradientEnergy = mean(Gx(:).^2 + Gy(:).^2);
result.sharpnessScore = gradientEnergy;

% Provisional threshold for sharpness
result.sharpnessPass = gradientEnergy >= 0.002;

% 5. Two-Tier Retinal Authenticity and Field-of-View Check
fovResult = checkRetinalField(img);

result.retinalAreaRatio  = fovResult.retinalAreaRatio;
result.cornerBrightness  = fovResult.cornerBrightness;
result.tierAPass         = fovResult.tierAPass;
result.tierBPass         = fovResult.tierBPass;
result.fovPass           = fovResult.fieldDetected;

% Record failed checks
if ~result.dimensionsPass
    result.reasons(end+1) = ...
        "Image dimensions are below 224 x 224 pixels.";
end

if ~result.brightnessPass
    result.reasons(end+1) = ...
        "Image may be too dark or too bright.";
end

if ~result.contrastPass
    result.reasons(end+1) = ...
        "Image contrast may be too low.";
end

if ~result.sharpnessPass
    result.reasons(end+1) = ...
        "Image may be blurred or lack visible detail.";
end

if ~result.fovPass
    result.reasons(end+1) = fovResult.message;
end

% Final decision
result.isUsable = result.dimensionsPass && ...
    result.brightnessPass && ...
    result.contrastPass && ...
    result.sharpnessPass && ...
    result.fovPass;

if result.isUsable
    result.status = "Preliminary checks passed";
    result.reasons = "No failure detected by the preliminary checks.";
end
end
