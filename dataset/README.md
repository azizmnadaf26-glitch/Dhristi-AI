# APTOS 2019 Blindness Detection Dataset

This directory contains the clinical ground-truth labels and evaluation metadata for the **APTOS 2019 Blindness Detection** diabetic retinopathy benchmark.

## Dataset Summary
- **Source:** Asia Pacific Tele-Ophthalmology Society (APTOS) 2019 Blindness Detection Competition (Kaggle)
- **Modality:** Color Fundus Photography
- **Total Labeled Cases:** 3,662 training images, 1,928 test images
- **Task:** 5-Class Ordinal Severity Grading of Diabetic Retinopathy (DR)

### Diabetic Retinopathy Severity Scale
| Grade | Severity Level | Clinical Features |
| :---: | :--- | :--- |
| **0** | No DR | No visible microvascular abnormalities |
| **1** | Mild NPDR | Microaneurysms only |
| **2** | Moderate NPDR | Microaneurysms, hemorrhages, hard/soft exudates |
| **3** | Severe NPDR | Any of: >20 intraretinal hemorrhages in each of 4 quadrants, definite venous beading in 2+ quadrants, prominent IRMA in 1+ quadrant (4-2-1 rule), no signs of PDR |
| **4** | Proliferative DR (PDR) | Neovascularization and/or vitreous/preretinal hemorrhage |

## Included Files
- `train.csv`: Contains the image identifiers (`id_code`) and ground truth clinical grade (`diagnosis`, 0–4).
- `test.csv`: Contains the image identifiers (`id_code`) for the independent evaluation holdout set.

## Downloading Full Raw Image Files (Optional for Re-Training)
The raw image archive is ~9.5 GB. If you wish to re-train the model or run complete offline validation on the entire set:

1. Install the Kaggle CLI:
   ```bash
   pip install kaggle
   ```
2. Download the dataset:
   ```bash
   kaggle competitions download -c aptos2019-blindness-detection
   ```
3. Extract `train_images/` and `test_images/` to this folder.

*Note: For testing and running the Dhristi-AI web application, sample test scans are already provided in `matlab/test_images/` and `frontend/public/retinal/`, and the pre-trained EfficientNet-B0 ONNX weights are included in `matlab/deployment_package/`.*

