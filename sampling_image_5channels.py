from cv2 import imread, imwrite
from os.path import join, splitext, exists
from os import listdir, mkdir
import numpy as np
# from scipy.misc import imread, imsave

base_dir_train = "../ISPRS_semantic_labeling_Vaihingen/train_5channels_test"
base_dir_validate = "../ISPRS_semantic_labeling_Vaihingen/validate_5channels_test"
base_dir_train_validate_gt = "../ISPRS_semantic_labeling_Vaihingen/train_validate_gt_5channels_test"

base_dir_top = "../ISPRS_semantic_labeling_Vaihingen/top"
base_dir_ndsm = "../ISPRS_semantic_labeling_Vaihingen/ndsm"
base_dir_dsm = "../ISPRS_semantic_labeling_Vaihingen/dsm"
base_dir_annotations = "../ISPRS_semantic_labeling_Vaihingen/annotations"

base_dir_tiny_train = "../ISPRS_semantic_labeling_Vaihingen/tiny_train_5channels"
base_dir_tiny_train_gt = "../ISPRS_semantic_labeling_Vaihingen/tiny_train_gt_5channels"

image_size = 224
num_cropping_per_image = 8
validate_image = ["top_mosaic_09cm_area7.png","top_mosaic_09cm_area17.png","top_mosaic_09cm_area23.png","top_mosaic_09cm_area37.png"]
# validate_image = []

def create_training_dataset():
    if not exists(base_dir_train):
        mkdir(base_dir_train)
    if not exists(base_dir_train_validate_gt):
        mkdir(base_dir_train_validate_gt)
    for filename in listdir(base_dir_annotations):
        if filename in validate_image:
            continue
        top_image = imread(join(base_dir_top, splitext(filename)[0] + ".tif"))
        annotation_image = imread(join(base_dir_annotations, filename), -1)
        dsm_image_name = filename.replace('top_mosaic', 'dsm').replace('png', 'tif').replace('area', 'matching_area')
        dsm_image = imread(base_dir_dsm + "/" + dsm_image_name, -1)
        print()
        print(np.shape(dsm_image))
        print(base_dir_dsm + "/" + dsm_image_name)
        ndsm_image_name = dsm_image_name.replace('.tif', '') + "_normalized.jpg"
        ndsm_image = imread(base_dir_ndsm + "/" + ndsm_image_name, -1)
        print(np.shape(ndsm_image))
        print()
        width = np.shape(top_image)[1]
        height = np.shape(top_image)[0]
        for i in range(num_cropping_per_image):
            x = int(np.random.uniform(0, height - image_size + 1))
            y = int(np.random.uniform(0, width - image_size + 1))
            print((x, y))
            top_image_cropped = top_image[x:x + image_size, y:y + image_size, :]
            ndsm_image_cropped = ndsm_image[x:x + image_size, y:y + image_size]
            ndsm_image_cropped = np.expand_dims(ndsm_image_cropped, axis = 2)
            dsm_image_cropped = dsm_image[x:x + image_size, y:y + image_size]
            dsm_image_cropped = np.expand_dims(dsm_image_cropped, axis = 2)
            array_to_save = np.concatenate((top_image_cropped,ndsm_image_cropped,dsm_image_cropped), axis=2).astype(dtype=np.float16)
            np.save(join(base_dir_train, splitext(filename)[0] + "_" + str(4 * i) + ".npy"), array_to_save)
            np.save(join(base_dir_train, splitext(filename)[0] + "_" + str(4 * i + 1) + ".npy"), np.fliplr(array_to_save))
            np.save(join(base_dir_train, splitext(filename)[0] + "_" + str(4 * i + 2) + ".npy"), np.flipud(array_to_save))
            np.save(join(base_dir_train, splitext(filename)[0] + "_" + str(4 * i + 3) + ".npy"), np.flipud(np.fliplr(array_to_save)))
            #imsave(join(base_dir_train, splitext(filename)[0] + "_" + str(i) + ".tif"), top_image_cropped)
            annotation_image_cropped = annotation_image[x:x + image_size, y:y + image_size]
            imwrite(join(base_dir_train_validate_gt, splitext(filename)[0] + "_" + str(4 * i) + ".png"), annotation_image_cropped)
            imwrite(join(base_dir_train_validate_gt, splitext(filename)[0] + "_" + str(4 * i + 1) + ".png"), np.fliplr(annotation_image_cropped))
            imwrite(join(base_dir_train_validate_gt, splitext(filename)[0] + "_" + str(4 * i + 2) + ".png"), np.flipud(annotation_image_cropped))
            imwrite(join(base_dir_train_validate_gt, splitext(filename)[0] + "_" + str(4 * i + 3) + ".png"), np.flipud(np.fliplr(annotation_image_cropped)))
    return None


def create_validation_dataset():
    if not exists(base_dir_validate):
        mkdir(base_dir_validate)
    for filename in validate_image:
        top_image = imread(join(base_dir_top, splitext(filename)[0] + ".tif"))
        annotation_image = imread(join(base_dir_annotations, filename), -1)
        dsm_image_name = filename.replace('top_mosaic', 'dsm').replace('png', 'tif').replace('area','matching_area')
        dsm_image = imread(base_dir_dsm + "/" + dsm_image_name, -1)
        ndsm_image_name = dsm_image_name.replace('.tif', '') + "_normalized.jpg"
        ndsm_image = imread(base_dir_ndsm + "/" + ndsm_image_name, -1)
        width = np.shape(top_image)[1]
        height = np.shape(top_image)[0]
        for i in range(num_cropping_per_image):
            x = int(np.random.uniform(0, height - image_size + 1))
            y = int(np.random.uniform(0, width - image_size + 1))
            print((x, y))
            top_image_cropped = top_image[x:x + image_size, y:y + image_size, :]
            ndsm_image_cropped = ndsm_image[x:x + image_size, y:y + image_size]
            ndsm_image_cropped = np.expand_dims(ndsm_image_cropped, axis=2)
            dsm_image_cropped = dsm_image[x:x + image_size, y:y + image_size]
            dsm_image_cropped = np.expand_dims(dsm_image_cropped, axis=2)
            array_to_save = np.concatenate((top_image_cropped, ndsm_image_cropped, dsm_image_cropped), axis=2).astype(dtype=np.float16)
            np.save(join(base_dir_validate, splitext(filename)[0] + "_" + str(i) + ".npy"), array_to_save)
            # imsave(join(base_dir_train, splitext(filename)[0] + "_" + str(i) + ".tif"), top_image_cropped)
            annotation_image_cropped = annotation_image[x:x + image_size, y:y + image_size]
            imwrite(join(base_dir_train_validate_gt, splitext(filename)[0] + "_" + str(i) + ".png"),
                        annotation_image_cropped)
    return None

if __name__=="__main__":
    np.random.seed(3796)
    create_training_dataset()
    create_validation_dataset()
