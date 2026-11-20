from pytorch3d.renderer import SoftSilhouetteShader
from pytorch3d.renderer.blending import sigmoid_alpha_blend


class BroadcastSilhouetteShader(SoftSilhouetteShader):
    def forward(self, fragments, meshes, **kwargs):
        colors = fragments.bary_coords.new_ones(()).expand_as(fragments.bary_coords)
        return sigmoid_alpha_blend(
            colors, fragments, kwargs.get("blend_params", self.blend_params)
        )


def install():
    from lib.common import render
    render.SoftSilhouetteShader = BroadcastSilhouetteShader
