"""
use rondom array replace objce witch was neglected
"""
import os
import cv2
import sys
import json
import argparse
import traceback
import numpy as np
import os.path as osp
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString

import utils
from datasets import get_dataset


def parse_args():
    parser = argparse.ArgumentParser(description="convert to voc dataset")
    parser.add_argument('--dataset', type=str, default='VisDrone',
                        choices=['VisDrone'], help='dataset name')
    parser.add_argument('--db_root', type=str, default="/home/visitor1/data/Visdrone",
                        help="dataset's root path")
    parser.add_argument('--imgsets', type=list, default=['train', 'val'],
                        choices=['train', 'val'], help='for train or test')
    args = parser.parse_args()
    return args

args = parse_args()


class MakeDataset(object):
    def __init__(self):
        self.dataset = get_dataset(args.dataset, args.db_root)

        self.region_dir = self.dataset.region_voc_dir
        self.segmentation_dir = self.region_dir + '/SegmentationClass'

        self.dest_datadir = self.dataset.detect_voc_dir
        self.image_dir = self.dest_datadir + '/JPEGImages'
        self.anno_dir = self.dest_datadir + '/Annotations'
        self.list_dir = self.dest_datadir + '/ImageSets/Main'
        self._init_path()

    def _init_path(self):
        if not osp.exists(self.dest_datadir):
            os.makedirs(self.dest_datadir)
            os.makedirs(self.image_dir)
            os.makedirs(self.anno_dir)
            os.makedirs(self.list_dir)

    def __call__(self):
        for imgset in args.imgsets:
            print("make {} detect dataset...".format(imgset))
            samples = self.dataset._load_samples(imgset)
            chip_ids= []
            chip_loc = dict()
            for i, sample in enumerate(samples):
                img_id = osp.basename(sample['image'])[:-4]
                sys.stdout.write('\rcomplete: {:d}/{:d} {:s}'
                            .format(i + 1, len(samples), img_id))
                sys.stdout.flush()
    
                chiplen, loc = self.make_chip(sample, imgset)
                for i in range(chiplen):
                    chip_ids.append('{}_{}'.format(img_id, i))
                chip_loc.update(loc)

            self.generate_imgset(chip_ids, imgset)

            # wirte chip loc json
            with open(osp.join(self.anno_dir, imgset+'_chip.json'), 'w') as f:
                json.dump(chip_loc, f)
                print('write loc json')

    def generate_region_gt(self, region_box, gt_bboxes, labels):
        chip_list = []
        neglect_list = []
        for box in region_box:
            chip_list.append(np.array(box))

        # chip gt
        chip_gt_list = []
        chip_label_list = []
        for chip in chip_list:
            chip_gt = []
            chip_label = []
            neglect_gt = []
            for i, box in enumerate(gt_bboxes):
                if utils.overlap(chip, box, 0.75):
                    box = [max(box[0], chip[0]), max(box[1], chip[1]), 
                        min(box[2], chip[2]), min(box[3], chip[3])]
                    new_box = [box[0] - chip[0], box[1] - chip[1],
                            box[2] - chip[0], box[3] - chip[1]]
                    chip_gt.append(np.array(new_box))
                    chip_label.append(labels[i])
                else utils.overlap(chip, box, 0.001):
                    box = [max(box[0], chip[0]), max(box[1], chip[1]), 
                        min(box[2], chip[2]), min(box[3], chip[3])]
                    new_box = [box[0] - chip[0], box[1] - chip[1],
                            box[2] - chip[0], box[3] - chip[1]]
                    neglect_gt.append(np.array(new_box))

            chip_gt_list.append(chip_gt)
            chip_label_list.append(chip_label)
            neglect_list.append(neglect_gt)

        return chip_list, chip_gt_list, chip_label_list, neglect_list

    def generate_imgset(self, img_list, imgset):
        with open(os.path.join(self.list_dir, imgset+'.txt'), 'w') as f:
            f.writelines([x + '\n' for x in img_list])
        print('\n%d images in %s set.' % (len(img_list), imgset))
        with open(os.path.join(self.list_dir, 'trainval.txt'), 'a') as f:
            f.writelines([x + '\n' for x in img_list])
        print('\n%d images in trainval set.' % len(img_list))

    def make_xml(self, chip, bboxes, labels, image_name, chip_size):
        node_root = Element('annotation')

        node_folder = SubElement(node_root, 'folder')
        node_folder.text = args.dataset

        node_filename = SubElement(node_root, 'filename')
        node_filename.text = image_name

        node_object_num = SubElement(node_root, 'object_num')
        node_object_num.text = str(len(bboxes))

        node_location = SubElement(node_root, 'location')
        node_loc_xmin = SubElement(node_location, 'xmin')
        node_loc_xmin.text = str(int(chip[0]) + 1)
        node_loc_ymin = SubElement(node_location, 'ymin')
        node_loc_ymin.text = str(int(chip[1]) + 1)
        node_loc_xmax = SubElement(node_location, 'xmax')
        node_loc_xmax.text = str(int(chip[2]) + 1)
        node_loc_ymax = SubElement(node_location, 'ymax')
        node_loc_ymax.text = str(int(chip[3]) + 1)

        node_size = SubElement(node_root, 'size')
        node_width = SubElement(node_size, 'width')
        node_width.text = str(chip_size[0])
        node_height = SubElement(node_size, 'height')
        node_height.text = str(chip_size[1])
        node_depth = SubElement(node_size, 'depth')
        node_depth.text = '3'

        for i, bbox in enumerate(bboxes):
            node_object = SubElement(node_root, 'object')
            node_name = SubElement(node_object, 'name')
            node_name.text = str(labels[i])
            node_difficult = SubElement(node_object, 'difficult')
            node_difficult.text = '0'

            # voc dataset is 1-based
            node_bndbox = SubElement(node_object, 'bndbox')
            node_xmin = SubElement(node_bndbox, 'xmin')
            node_xmin.text = str(int(bbox[0]) + 1)
            node_ymin = SubElement(node_bndbox, 'ymin')
            node_ymin.text = str(int(bbox[1]) + 1)
            node_xmax = SubElement(node_bndbox, 'xmax')
            node_xmax.text = str(int(bbox[2] + 1))
            node_ymax = SubElement(node_bndbox, 'ymax')
            node_ymax.text = str(int(bbox[3] + 1))

        xml = tostring(node_root, encoding='utf-8')
        dom = parseString(xml)
        # print(xml)
        return dom        

    def make_chip(self, sample, imgset):
        image = cv2.imread(sample['image'])
        height, width = sample['height'], sample['width']
        img_id = osp.basename(sample['image'])[:-4]

        mask_path = osp.join(self.segmentation_dir, '{}.png'.format(img_id))
        mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
        mask_h, mask_w = mask.shape[:2]

        # make chip
        region_box, contours = utils.generate_box_from_mask(mask)
        region_box = utils.region_postprocess(region_box, contours, (mask_w, mask_h))
        region_box = utils.resize_box(region_box, (mask_w, mask_h), (width, height))
        region_box = utils.generate_crop_region(region_box, (width, height))

        # if imgset == 'train':
        #     region_box = np.vstack((region_box, np.array([0, 0, width-1, height-1])))

        gt_bboxes, gt_cls = sample['bboxes'], sample['cls']

        chip_list, chip_gt_list, chip_label_list, neglect_list = self.generate_region_gt(
            region_box, gt_bboxes, gt_cls)
        chip_loc = self.write_chip_and_anno(
            image, img_id, chip_list, chip_gt_list, chip_label_list, neglect_list)

        return len(chip_list), chip_loc

    def write_chip_and_anno(self, image, img_id, 
        chip_list, chip_gt_list, chip_label_list, neglect_list):
        """write chips of one image to disk and make xml annotations
        """
        assert len(chip_gt_list) > 0
        chip_loc = dict()
        for i, chip in enumerate(chip_list):
            img_name = '{}_{}.jpg'.format(img_id, i)
            xml_name = '{}_{}.xml'.format(img_id, i)
            chip_loc[img_name] = [int(x) for x in chip]
            chip_size = (chip[2] - chip[0], chip[3] - chip[1])  #w, h

            chip_img = image[chip[1]:chip[3], chip[0]:chip[2], :].copy()
            assert len(chip_img.shape) == 3
            for neg_box in neglect_list[i]:
                neg_w = neg_box[2] - neg_box[0]
                neg_h = neg_box[3] - neg_box[1]
                random_box = np.random.rand(neg_h, neg_w, 3) * 255
                chip_img[neg_box[1]:neg_box[3], neg_box[0]:neg_box[2], :] = random_box

            bbox = np.array(chip_gt_list[i], dtype=np.int)
            label = np.array(chip_label_list[i], dtype=np.int)
            dom = self.make_xml(chip, bbox, label, img_name, chip_size)

            cv2.imwrite(os.path.join(self.image_dir, img_name), chip_img)
            with open(os.path.join(self.anno_dir, xml_name), 'w') as f:
                f.write(dom.toprettyxml(indent='\t', encoding='utf-8').decode('utf-8')) 
        return chip_loc


if __name__ == "__main__":
    makedataset = MakeDataset()
    makedataset()