
function result = generateRetinaGradCAM(net, img, classIndex)

if isempty(net)
    error('RetinaGuide:EmptyModel', ...
        'The model is not loaded.');
end

if isempty(img)
    error('RetinaGuide:EmptyImage', ...
        'No image was provided.');
end

% Convert input to RGB
if ndims(img) == 2
    img = repmat(img, 1, 1, 3);
elseif size(img, 3) == 4
    img = img(:, :, 1:3);
elseif size(img, 3) ~= 3
    error('RetinaGuide:InvalidImage', ...
        'Image must be grayscale, RGB, or RGBA.');
end

% Convert image to uint8
if isa(img, 'uint8')
    % Keep unchanged
elseif isa(img, 'uint16')
    img = uint8(double(img) / 65535 * 255);
elseif isfloat(img)
    img = uint8(round(min(max(img, 0), 1) * 255));
else
    img = im2uint8(img);
end

% Match model preprocessing
resizedImg = imresize(img, [384 384], 'bilinear');
resizedImg = im2single(resizedImg);

meanRGB = reshape(single([0.485 0.456 0.406]), 1, 1, 3);
stdRGB  = reshape(single([0.229 0.224 0.225]), 1, 1, 3);

normalizedImg = (resizedImg - meanRGB) ./ stdRGB;

dlInput = dlarray( ...
    reshape(normalizedImg, 384, 384, 3, 1), 'SSCB');

% Generate Grad-CAM
scoreMap = gradCAM(net, dlInput, classIndex, ...
    'FeatureLayer', 'x_features_featu_470', ...
    'ReductionLayer', 'x_classifier_classif', ...
    'ExecutionEnvironment', 'cpu');

% Normalize importance map for display
scoreMap = double(extractdata(scoreMap));
scoreMap = squeeze(scoreMap);

scoreMap = max(scoreMap, 0);

if max(scoreMap(:)) > 0
    scoreMap = scoreMap ./ max(scoreMap(:));
end

% Prepare result
result.scoreMap = scoreMap;
result.originalImage = resizedImg;
result.classIndex = classIndex;

end
