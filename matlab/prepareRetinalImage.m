
function [rgbImage, info] = prepareRetinalImage(img)
% PREPARERETINALIMAGE Validate and standardise a retinal image.
% Converts supported grayscale/RGB images into uint8 RGB.
% Model-specific resizing and normalization are performed separately.

if isempty(img)
    error('RetinaGuide:EmptyImage', ...
        'The input image is empty.');
end

if ~(isnumeric(img) || islogical(img)) || ...
        ~isreal(img) || issparse(img)
    error('RetinaGuide:InvalidType', ...
        'Input must be a real, full numeric or logical image.');
end

if ndims(img) > 3
    error('RetinaGuide:InvalidDimensions', ...
        'Input must be a 2-D or 3-D image.');
end

originalSize = size(img);

% Convert grayscale to three-channel RGB.
if ismatrix(img)
    img = repmat(img, [1 1 3]);

elseif size(img, 3) == 4
    % Discard the alpha channel.
    img = img(:, :, 1:3);

elseif size(img, 3) ~= 3
    error('RetinaGuide:InvalidChannels', ...
        'Input must have 1, 3, or 4 channels.');
end

% Convert the image to uint8 safely.
if islogical(img)
    img = uint8(img) .* 255;

elseif isa(img, 'uint8')
    % Already in the required format.

elseif isinteger(img)
    img = im2uint8(img);

elseif isfloat(img)
    if any(~isfinite(img(:)))
        error('RetinaGuide:InvalidPixels', ...
            'Image contains NaN or Inf values.');
    end

    if isempty(img) || min(img(:)) < 0 || max(img(:)) > 1
        error('RetinaGuide:InvalidRange', ...
            'Floating-point images must have values in [0, 1].');
    end

    img = im2uint8(img);

else
    error('RetinaGuide:UnsupportedType', ...
        'Unsupported image data type.');
end

rgbImage = img;

% Return metadata for logging and verification.
info.originalSize = originalSize;
info.outputSize = size(rgbImage);
info.outputClass = class(rgbImage);
info.channelCount = size(rgbImage, 3);
info.status = 'Image prepared successfully';
end
