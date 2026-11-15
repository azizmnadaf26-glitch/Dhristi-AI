# Graded Retinal Test Scans & Quality Test Images

This directory provides pre-sorted, high-resolution retinal fundus images for live testing, demonstration, and validation across all Diabetic Retinopathy severity grades and edge cases.

---

## 🎯 Clinical DR Severity Benchmark Images

Use these images in the Web UI to test multi-class inference and Grad-CAM explainability:

| DR Severity Level | Folder | Sample Images | Expected Clinical Features |
| :--- | :--- | :--- | :--- |
| **Grade 0: No DR** | `Grade_0_No_DR/` | `Grade_0_Image_01.png`<br>`Grade_0_Image_02.png` | Normal, healthy retina; crisp vessels and macula; 0 microaneurysms. |
| **Grade 1: Mild NPDR** | `Grade_1_Mild_DR/` | `Grade_1_Image_01.png`<br>`Grade_1_Image_02.png` | Isolated microaneurysms only. Non-referable early stage. |
| **Grade 2: Moderate NPDR** | `Grade_2_Moderate_DR/` | `Grade_2_Image_01.png`<br>`Grade_2_Image_02.png` | Multiple microaneurysms, blot hemorrhages, hard/cotton wool exudates. |
| **Grade 3: Severe NPDR** | `Grade_3_Severe_DR/` | `Grade_3_Image_01.png`<br>`Grade_3_Image_02.png` | Meets 4-2-1 rule: extensive hemorrhages across 4 quadrants or venous beading. |
| **Grade 4: Proliferative DR** | `Grade_4_Proliferative_DR/` | `Grade_4_Image_01.png`<br>`Grade_4_Image_02.png` | Neovascularization (NVD/NVE), fibrous proliferation, high blindness risk. |

---

## 🔍 Image Quality Pre-Screening Tests

Located in `quality_tests/`:
- `dark_test.jpeg`: Severe under-exposure / dark illumination. Triggers pre-screening quality rejection.
- `blurred_test.jpeg`: Out-of-focus capture. Triggers blur warning for clinician recapture.
- `low_contrast_test.jpeg`: Insufficient contrast between fundus background and vascular tree.

---

## 📋 Manifest

See `presentation_manifest.csv` for verified ground truth labels, model predictions, and confidence scores for each sample image.
