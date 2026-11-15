
function info = getDRGradeInfo(grade)
% GETDRGRADEINFO Return APTOS-compatible DR grade descriptions.
% These descriptions are for research and educational use only.

validateattributes(grade, {'numeric'}, ...
    {'real', 'finite', 'scalar', 'integer', '>=', 0, '<=', 4});

labels = {
    'No DR'
    'Mild DR'
    'Moderate DR'
    'Severe DR'
    'Proliferative DR'
    };

descriptions = {
    'No diabetic retinopathy detected by the grading reference.'
    'Mild non-proliferative diabetic retinopathy.'
    'Moderate non-proliferative diabetic retinopathy.'
    'Severe non-proliferative diabetic retinopathy.'
    'Proliferative diabetic retinopathy.'
    };

info.grade = grade;
info.label = labels{grade + 1};
info.description = descriptions{grade + 1};
info.status = 'Grade information retrieved';
info.disclaimer = ...
    'Research support only; clinical assessment requires a qualified professional.';
end
