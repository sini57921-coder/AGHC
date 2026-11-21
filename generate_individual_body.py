"""Generate same-task canonical and original-pose body meshes.

The entry point is import-safe. Third-party ECON/SMPL-X runtime modules are
loaded only when generation is requested and only from the configured ECON
source directory.
"""
import json
import sys
from pathlib import Path

from release_config import path as config_path
from body_mesh_task import generate as generate_meshes


def generate_individual_body(parameter, canonical, original, output, height_cm):
    import numpy as np
    import torch
    import trimesh

    econ_root = str(config_path('econ_source'))
    if econ_root not in sys.path:
        sys.path.insert(0, econ_root)
    from lib import smplx

    parameter, original, output = Path(parameter), Path(original), Path(output)
    data = np.load(parameter, allow_pickle=True).item()
    beta = data['betas'].float().reshape(1, -1)
    model = smplx.create(str(config_path('smpl_models')), model_type='smplx',
                         gender='neutral', ext='npz', num_betas=beta.numel(),
                         num_expression_coeffs=data['expression'].numel(), use_pca=False,
                         flat_hand_mean=True)
    with torch.no_grad():
        vertices = model(betas=beta, body_pose=data['body_pose'].reshape(1, -1),
                         global_orient=data['global_orient'].reshape(1, -1),
                         left_hand_pose=data['left_hand_pose'].reshape(1, -1),
                         right_hand_pose=data['right_hand_pose'].reshape(1, -1),
                         jaw_pose=data['jaw_pose'].reshape(1, -1),
                         expression=data['expression'].reshape(1, -1)).vertices[0]
        vertices = ((vertices + data['transl'].reshape(1, 3)) * data['scale']).numpy() * [1, -1, -1]
    reference = trimesh.load(original, process=False)
    if vertices.shape != reference.vertices.shape:
        raise ValueError('original body vertex correspondence unavailable')
    distance = np.linalg.norm(vertices - reference.vertices, axis=1)
    body_height = np.ptp(reference.vertices[:, 1])
    if distance.mean() > .01 * body_height or distance.max() > .03 * body_height:
        raise ValueError('regenerated body does not match ECON coordinates')
    result = generate_meshes(parameter, canonical, original, output, float(height_cm))
    factor = result['uniform_scale_m_per_econ_unit']
    body_path = output / 'body_original_pose_regenerated_m.obj'
    trimesh.Trimesh(vertices=vertices * factor, faces=reference.faces, process=False).export(body_path)
    result.update(body_original_path=str(body_path), original_vertex_mean_distance=float(distance.mean()),
                  original_vertex_max_distance=float(distance.max()),
                  scale_source='35维身高 / 同一SMPL-X体形规范姿态高度，统一各方向缩放')
    (output / 'individual_body_result.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    parameter, canonical, original, output, height = args
    result = generate_individual_body(parameter, canonical, original, output, height)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
