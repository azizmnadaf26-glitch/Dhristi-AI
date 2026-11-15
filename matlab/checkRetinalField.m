function result = checkRetinalField(img)
% CHECKRETINALFIELD
% Two-tier retinal field-of-view and domain authenticity check.
% Evaluates:
%   1. Optical FOV area coverage (foreground non-dark ratio >= 0.20)
%   2. Tier A: Corner darkness assessment (corner brightness <= 0.12)
%   3. Tier B: Chromatic fundus profile (red channel dominance)

result = struct();
result.status = "Review required";
result.retinalAreaRatio = 0;
result.cornerBrightness = 1.0;
result.redToGreenRatio = 0;
result.redToBlueRatio = 0;
result.tierAPass = false;
result.tierBPass = false;
result.fieldDetected = false;
result.message = "";

if isempty(img) || (~isnumeric(img) && ~islogical(img))
    result.message = "Invalid or empty image.";
    return;
end

if ndims(img) == 3
    if size(img, 3) ~= 3
        result.message = "Unsupported image channels.";
        return;
    end
    imgD = im2double(img);
    gray = rgb2gray(imgD);
elseif ndims(img) == 2
    imgD = repmat(im2double(img), [1 1 3]);
    gray = im2double(img);
else
    result.message = "Unsupported image dimensions.";
    return;
end

% 1. Optical FOV Area Coverage
mask = gray > 0.05;
mask = imfill(mask, "holes");
mask = bwareafilt(mask, 1);
result.retinalAreaRatio = nnz(mask) / numel(mask);
fovPass = result.retinalAreaRatio >= 0.20;

% 2. Tier A: Corner Darkness Assessment
[H, W, ~] = size(imgD);
cH = max(1, round(0.04 * H));
cW = max(1, round(0.04 * W));
cornerVal = mean([ ...
    mean(mean(gray(1:cH, 1:cW))), ...
    mean(mean(gray(1:cH, end-cW+1:end))), ...
    mean(mean(gray(end-cH+1:end, 1:cW))), ...
    mean(mean(gray(end-cH+1:end, end-cW+1:end))) ...
]);
result.cornerBrightness = cornerVal;
result.tierAPass = cornerVal <= 0.12;

% 3. Tier B: Chromatic Fundus Profile
rMean = mean(mean(imgD(:,:,1)));
gMean = mean(mean(imgD(:,:,2)));
bMean = mean(mean(imgD(:,:,3)));
result.redToGreenRatio = rMean / (gMean + 1e-4);
result.redToBlueRatio  = rMean / (bMean + 1e-4);
result.tierBPass = (rMean >= 0.95 * gMean) && (rMean >= 1.00 * bMean);

% Combined 2-Tier Decision
result.fieldDetected = fovPass && result.tierAPass && result.tierBPass;

if result.fieldDetected
    result.status = "Preliminary field detected";
    result.message = "A sufficiently large non-dark region and valid retinal chromatic profile were detected.";
elseif ~result.tierAPass
    result.status = "Non-retinal boundary detected";
    result.message = "Image corners do not exhibit expected fundus camera dark border aperture (corner brightness exceeded 0.12).";
elseif ~result.tierBPass
    result.status = "Non-retinal chromatic profile";
    result.message = "Color distribution does not match retinal vascular/choroidal profile (red channel is not dominant).";
else
    result.status = "Review required";
    result.message = "Retinal field may be missing or too small.";
end

end
