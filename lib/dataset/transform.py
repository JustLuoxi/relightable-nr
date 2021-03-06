import os

import numpy as np

import torch
import torch.nn.functional as F
import torchvision.transforms as T

import collections

import random
from PIL import Image

from dataset.data_util import calc_center
from dataset.data_util import rodrigues_rotation_matrix


class RandomTransform(object):
    def __init__(self, size, max_shift = 0, max_scale = 0, max_rotation = 0, interpolation=Image.BICUBIC, isTrain = True, is_center = False):
        assert isinstance(size, int) or (isinstance(size, collections.abc.Iterable) and len(size) == 2)

        self.size = size
        self.interpolation = interpolation
        self.max_shift = max_shift
        self.max_scale = max_scale
        self.min_scale = 1.0 - (max_scale - 1.0) / 2.0
        self.isTrain = isTrain
        self.max_rotation = max_rotation
        self.is_center = is_center

    def __call__(self, img, K = None, Tc = None,  mask = None):

        # change extrinsic from "world2cam" to "cam2world"
        Tc = np.linalg.inv(Tc)

        K = torch.from_numpy(K.astype(np.float32))
        Tc = torch.from_numpy(Tc.astype(np.float32))

        img_np = np.asarray(img)

        offset_x = random.randint(-self.max_shift, self.max_shift)
        offset_y = random.randint(-self.max_shift, self.max_shift)

        rotation = (random.random()-0.5)*np.deg2rad(self.max_rotation)
        ration = random.random() * (self.max_scale - self.min_scale) + self.min_scale
                
        width, height = img.size
        R = torch.Tensor(rodrigues_rotation_matrix(np.array([0,0,1]),rotation))     
        Tc[0:3,0:3] = torch.matmul(Tc[0:3,0:3],R)
        m_scale = height/self.size[0]

        cx, cy = 0, 0

        if mask is not None and self.isTrain:
            mask_np = np.asarray(mask)
            if len(mask_np.shape)>2:
                mask_np = mask_np[:,:,0]
            cy, cx = calc_center(mask_np)
     
            cx = cx - width /2
            cy = cy - height/2
            
        translation = (offset_x*m_scale-cx,offset_y*m_scale-cy )

        if self.is_center:
            translation = [width /2-K[0,2],height/2-K[1,2]]
            translation = list(translation)
            ration = 1.05
            
            if (self.size[1]/2)/(self.size[0]*ration  / height) - K[0,2] != translation[0] :
                ration = 1.2
            translation[1] = (self.size[0]/2)/(self.size[0]*ration  / height) - K[1,2]
            translation[0] = (self.size[1]/2)/(self.size[0]*ration  / height) - K[0,2]
            translation = tuple(translation)

        #translation = (width /2-K[0,2],height/2-K[1,2])
        
        img = T.functional.rotate(img, angle = np.rad2deg(rotation), resample = Image.BICUBIC, center =(K[0,2],K[1,2]))
        img = T.functional.affine(img, angle = 0, translate = translation, scale= 1,shear=0)
        img = T.functional.crop(img, 0, 0,  int(height/ration),int(height*self.size[1]/ration/self.size[0]) )
        img = T.functional.resize(img, self.size, self.interpolation)
        img = T.functional.to_tensor(img)
        
        ROI = np.ones_like(img_np)*255.0

        ROI = Image.fromarray(np.uint8(ROI))
        ROI = T.functional.rotate(ROI, angle = np.rad2deg(rotation), resample = Image.BICUBIC, center =(K[0,2],K[1,2]))
        ROI = T.functional.affine(ROI, angle = 0, translate = translation, scale= 1,shear=0)
        ROI = T.functional.crop(ROI, 0,0, int(height/ration),int(height*self.size[1]/ration/self.size[0]) )
        ROI = T.functional.resize(ROI, self.size, self.interpolation)
        ROI = T.functional.to_tensor(ROI)
        ROI = ROI[0:1,:,:]
        
        if mask is not None:
            mask = T.functional.rotate(mask, angle = np.rad2deg(rotation), resample = Image.BICUBIC, center =(K[0,2],K[1,2]))
            mask = T.functional.affine(mask, angle = 0, translate = translation, scale= 1,shear=0)
            mask = T.functional.crop(mask, 0, 0,  int(height/ration),int(height*self.size[1]/ration/self.size[0]) )
            mask = T.functional.resize(mask, self.size, self.interpolation)
            mask = T.functional.to_tensor(mask)

        #K = K / m_scale
        #K[2,2] = 1

        K[0,2] = K[0,2] + translation[0]
        K[1,2] = K[1,2] + translation[1]

        s = self.size[0] * ration / height

        K = K*s

        K[2,2] = 1  

        K = K.numpy()
        Tc = Tc.numpy()

        # change extrinsic from "cam2world" to "world2cam"
        Tc = np.linalg.inv(Tc)
        return img, K, Tc, mask, ROI
    
    def __repr__(self):
        return self.__class__.__name__ + '()'