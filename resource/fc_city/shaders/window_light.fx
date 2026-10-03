// Time-responsive emissive glazing; no dynamic shadow-map or GI claim.
texture gTexture;
float gNight = 0.0;
float gEmission = 0.30;
float3 gWindowTint = float3(1.0, 0.73, 0.46);
float gDayScale = 0.58;

sampler BaseSampler = sampler_state {
    Texture = <gTexture>;
    MinFilter = Linear; MagFilter = Linear; MipFilter = Linear;
    AddressU = Wrap; AddressV = Wrap;
};

float4 PSMain(float2 uv : TEXCOORD0, float4 vertexColor : COLOR0) : COLOR0 {
    float4 base = tex2D(BaseSampler, uv) * vertexColor;
    float micro = 0.96 + 0.04 * sin(uv.x * 31.0 + uv.y * 19.0);
    float3 day = base.rgb * gDayScale;
    float3 night = base.rgb + gWindowTint * gEmission;
    return float4(saturate(lerp(day, night, saturate(gNight)) * micro), base.a);
}

technique WindowLighting {
    pass P0 {
        PixelShader = compile ps_2_0 PSMain();
    }
}
