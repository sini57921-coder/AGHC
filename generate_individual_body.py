from release_config import path as config_path
import json
import sys
from pathlib import Path

import numpy as np
import torch
import trimesh
from lib import smplx

from body_mesh_task import generate

parameter, canonical, original, output, height = sys.argv[1:]
parameter, original, output = Path(parameter), Path(original), Path(output)
d = np.load(parameter, allow_pickle=True).item()
beta = d['betas'].float().reshape(1, -1)
model = smplx.create(str(config_path('smpl_models')), model_type='smplx',
                     gender='neutral', ext='npz', num_betas=beta.numel(),
                     num_expression_coeffs=d['expression'].numel(), use_pca=False, flat_hand_mean=True)
with torch.no_grad():
    vertices = model(betas=beta, body_pose=d['body_pose'].reshape(1, -1),
                     global_orient=d['global_orient'].reshape(1, -1),
                     left_hand_pose=d['left_hand_pose'].reshape(1, -1),
                     right_hand_pose=d['right_hand_pose'].reshape(1, -1),
                     jaw_pose=d['jaw_pose'].reshape(1, -1), expression=d['expression'].reshape(1, -1)).vertices[0]
    vertices = ((vertices + d['transl'].reshape(1, 3)) * d['scale']).numpy() * [1, -1, -1]
reference = trimesh.load(original, process=False)
if vertices.shape != reference.vertices.shape:
    raise ValueError('original body vertex correspondence unavailable')
distance = np.linalg.norm(vertices - reference.vertices, axis=1)
body_height = np.ptp(reference.vertices[:, 1])
if distance.mean() > .01 * body_height or distance.max() > .03 * body_height:
    raise ValueError('regenerated body does not match ECON coordinates')
result = generate(parameter, canonical, original, output, float(height))
factor = result['uniform_scale_m_per_econ_unit']
body_path = output / 'body_original_pose_regenerated_m.obj'
trimesh.Trimesh(vertices=vertices * factor, faces=reference.faces, process=False).export(body_path)
result.update(body_original_path=str(body_path), original_vertex_mean_distance=float(distance.mean()),
              original_vertex_max_distance=float(distance.max()),
              scale_source='35维身高 / 同一SMPL-X体形规范姿态高度，统一各方向缩放')
(output / 'individual_body_result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
