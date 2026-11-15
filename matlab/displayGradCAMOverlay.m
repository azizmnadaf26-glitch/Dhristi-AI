
function displayGradCAMOverlay(ax, retinalImage, heatmap)
% DISPLAYGRADCAMOVERLAY Display a supplied Grad-CAM heatmap over an image.
% The heatmap must come from an actual model explanation.
% This function does not generate Grad-CAM.

if ~isgraphics(ax, 'axes')
    error('RetinaGuide:InvalidAxes', ...
        'Provide a valid MATLAB axes or UIAxes.');
end

if isempty(retinalImage) || ...
        ~(isnumeric(retinalImage) || islogical(retinalImage)) || ...
        ndims(retinalImage) > 3 || ...
        (ndims(retinalImage) == 3 && ...
        ~ismember(size(retinalImage, 3), [1 3 4]))
    error('RetinaGuide:InvalidImage', ...
        'Provide a valid grayscale, RGB, or RGBA image.');
end

if isempty(heatmap) || ~isnumeric(heatmap) || ...
        ~isreal(heatmap) || ~ismatrix(heatmap) || ...
        any(~isfinite(heatmap(:)))
    error('RetinaGuide:InvalidHeatmap', ...
        'Heatmap must be a finite, real numeric matrix.');
end

heatmap = double(heatmap);

if max(heatmap(:)) == min(heatmap(:))
    error('RetinaGuide:EmptyActivation', ...
        'Heatmap has no variation and cannot provide a useful overlay.');
end

% Scale activations to [0, 1].
heatmap = heatmap - min(heatmap(:));
heatmap = heatmap ./ max(heatmap(:));

% Convert the source image to RGB for display.
if ismatrix(retinalImage)
    retinalImage = repmat(retinalImage, [1 1 3]);
elseif size(retinalImage, 3) == 4
    retinalImage = retinalImage(:, :, 1:3);
end

if islogical(retinalImage)
    retinalImage = uint8(retinalImage) .* 255;
elseif isa(retinalImage, 'uint8')
    % No conversion needed.
elseif isinteger(retinalImage)
    retinalImage = im2uint8(retinalImage);
elseif isfloat(retinalImage)
    if any(~isfinite(retinalImage(:))) || ...
            min(retinalImage(:)) < 0 || max(retinalImage(:)) > 1
        error('RetinaGuide:InvalidImageRange', ...
            'Floating-point image values must be in [0, 1].');
    end
    retinalImage = im2uint8(retinalImage);
else
    error('RetinaGuide:UnsupportedImageType', ...
        'Unsupported retinal image type.');
end

% Resize the supplied heatmap to match the retinal image.
heatmap = imresize(heatmap, ...
    [size(retinalImage, 1), size(retinalImage, 2)]);

cla(ax);
imshow(retinalImage, 'Parent', ax);
hold(ax, 'on');

overlay = imagesc(ax, heatmap);
set(overlay, 'AlphaData', 0.45 .* heatmap);

colormap(ax, 'jet');
clim(ax, [0 1]);
axis(ax, 'image');
axis(ax, 'off');

title(ax, 'Grad-CAM Explanation');
hold(ax, 'off');
end
