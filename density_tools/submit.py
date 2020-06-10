import os
import cv2
import json
import utils
import zipfile
import numpy as np
import os.path as osp
from tqdm import tqdm

hyp = {
    'result': "/home/twsf/work/CRGNet/chip_results.json",
    'local': "/home/twsf/data/Visdrone/density_chip/Locations/test_chip.json",
    'submit_dir': './results',
    'show': False,
    'srcimg_dir': "/home/twsf/data/Visdrone/test/images/"
}


class Submit(object):
    def __init__(self):
        self.srcimg_dir = hyp['srcimg_dir']
        if not osp.exists(hyp['submit_dir']):
            os.mkdir(hyp['submit_dir'])

    def __call__(self):
        # get val predict box
        with open(hyp['result'], 'r') as f:
            results = json.load(f)
        with open(hyp['local'], 'r') as f:
            chip_loc = json.load(f)
        detecions = dict()
        for det in tqdm(results):
            img_id = det['image_id']
            cls_id = det['category_id']
            bbox = det['bbox']
            score = det['score']
            loc = chip_loc[img_id]
            bbox = [bbox[0] + loc[0], bbox[1] + loc[1], bbox[2] + loc[0], bbox[3] + loc[1]]
            img_name = '_'.join(img_id.split('_')[:-1]) + osp.splitext(img_id)[1]
            if img_name in detecions:
                detecions[img_name].append(bbox + [score, cls_id])
            else:
                detecions[img_name] = [bbox + [score, cls_id]]

        # merge
        results = []
        for img_name, det in tqdm(detecions.items()):
            det = utils.nms(det, score_threshold=0.05, iou_threshold=0.6, overlap_threshold=1).astype(np.float32)

            # save
            with open(osp.join(hyp['submit_dir'], img_name[:-4]+'.txt'), "w") as f:
                det[:, 5] += 1
                for box in det:
                    bbox = [str(x) for x in (list(box[0:6]) + [-1, -1])]
                    f.write(','.join(bbox) + '\n')

            # show
            if hyp['show']:
                img = cv2.imread(osp.join(self.srcimg_dir, img_name))
                utils.show_image(img, det)

        # Zip
        result_files = [osp.join(hyp['submit_dir'], file) for file in os.listdir(hyp['submit_dir'],)]
        zip_path = 'result.zip'
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip:
            for file in result_files:
                if ".txt" in file:
                    zip.write(file)


if __name__ == '__main__':
    det = Submit()
    det()