function result = runRetinaInference(net, img)
% RUNRETINAINFERENCE
% Runs five-class EfficientNet-B0 inference using the
% verified Fold 2 legacy ONNX deployment model with
% post-hoc temperature calibration (T = 2.7600).

if isempty(net)
    error('RetinaGuide:EmptyModel', ...
        'The ONNX model is not loaded.');
end

if isempty(img)
    error('RetinaGuide:EmptyImage', ...
        'No retinal image was provided.');
end

% 1. Handle grayscale and RGBA images
if ndims(img) == 2
    img = repmat(img, 1, 1, 3);
elseif size(img, 3) == 4
    img = img(:, :, 1:3);
elseif size(img, 3) ~= 3
    error('RetinaGuide:InvalidImage', ...
        'Image must be grayscale, RGB, or RGBA.');
end

% 2. Convert image to RGB uint8
if isa(img, 'uint8')
    img = img;
elseif isa(img, 'uint16')
    img = uint8(double(img) / 65535 * 255);
elseif isfloat(img)
    img = uint8(round(min(max(img, 0), 1) * 255));
else
    img = im2uint8(img);
end

% 3. Resize to model input dimensions
resizedImg = imresize(img, [384 384], 'bilinear');

% 4. Convert to single precision [0,1]
resizedImg = im2single(resizedImg);

% 5. ImageNet normalization
meanRGB = reshape(single([0.485 0.456 0.406]), 1, 1, 3);
stdRGB  = reshape(single([0.229 0.224 0.225]), 1, 1, 3);

normalizedImg = (resizedImg - meanRGB) ./ stdRGB;

% 6. Create SSCB input
inputData = reshape(normalizedImg, 384, 384, 3, 1);
dlInput = dlarray(inputData, 'SSCB');

% 7. Run ONNX inference (raw logits from layer 243)
logits = predict(net, dlInput);
logits = extractdata(logits);
logits = double(logits(:));

% 8. Convert logits into raw and calibrated probabilities
shiftedLogits = logits - max(logits);
rawProbs = exp(shiftedLogits);
rawProbs = rawProbs ./ sum(rawProbs);

% Post-Hoc Temperature Calibration (T = 2.7600 fitted on calibration dataset)
T = 2.7600;
calibratedShifted = shiftedLogits ./ T;
calibratedProbs = exp(calibratedShifted);
calibratedProbs = calibratedProbs ./ sum(calibratedProbs);

% 9. Identify predicted class (ranking is invariant under monotonic T > 0)
classNames = {
    'No DR'
    'Mild'
    'Moderate'
    'Severe'
    'Proliferative'
    };

[rawConf, predictedIndex] = max(rawProbs);
calibratedConf = calibratedProbs(predictedIndex);

% 10. Return structured results
result.logits = logits;
result.rawProbabilities = rawProbs;
result.rawConfidence = rawConf;
result.calibratedProbabilities = calibratedProbs;
result.calibratedConfidence = calibratedConf;
result.temperature = T;

% Primary public outputs (calibrated to prevent artificial 100% saturation)
result.probabilities = calibratedProbs;
result.confidence = calibratedConf;
result.predictedIndex = predictedIndex;
result.predictedGrade = predictedIndex - 1;
result.predictedClass = classNames{predictedIndex};
result.resizedImage = resizedImg;

end
