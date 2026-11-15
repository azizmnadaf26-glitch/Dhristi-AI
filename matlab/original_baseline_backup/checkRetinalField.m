
function result = checkRetinalField(img)
% Preliminary retinal field-of-view check.
% This is an engineering heuristic, not a clinical validation.

result = struct();
result.status = "Review required";
result.retinalAreaRatio = 0;
result.fieldDetected = false;
result.message = "";

if isempty(img) || ~isnumeric(img) && ~islogical(img)
    result.message = "Invalid or empty image.";
    return;
end

if ndims(img) == 3
    if size(img, 3) ~= 3
        result.message = "Unsupported image channels.";
        return;
    end
    gray = im2gray(im2double(img));
elseif ndims(img) == 2
    gray = im2double(img);
else
    result.message = "Unsupported image dimensions.";
    return;
end

% Identify pixels brighter than the black background.
mask = gray > 0.05;

% Keep the largest connected region.
mask = imfill(mask, "holes");
mask = bwareafilt(mask, 1);

result.retinalAreaRatio = nnz(mask) / numel(mask);

% Preliminary threshold; validate on more images later.
result.fieldDetected = result.retinalAreaRatio >= 0.20;

if result.fieldDetected
    result.status = "Preliminary field detected";
    result.message = "A sufficiently large non-dark region was detected.";
else
    result.message = "Retinal field may be missing or too small.";
end
end
