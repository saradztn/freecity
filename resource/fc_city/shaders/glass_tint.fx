// Mild time-of-day tint only; no depth-aware reflection is available here.
texture gTexture;
float3 gSkyTint = float3(0.70,0.79,0.86);
float gNight = 0.0;
sampler BaseSampler = sampler_state {
    Texture = <gTexture>;
    MinFilter = Linear; MagFilter = Linear; MipFilter = Linear;
    AddressU = Wrap; AddressV = Wrap;
};
float4 PSMain(float2 uv : TEXCOORD0, float4 vertexColor : COLOR0) : COLOR0 {
    float4 base=tex2D(BaseSampler,uv)*vertexColor;
    float3 nightTint=float3(0.37,0.45,0.54);
    float3 tint=lerp(gSkyTint,nightTint,saturate(gNight));
    return float4(saturate(lerp(base.rgb,tint,0.12)),base.a);
}
technique GlassTint {
    pass P0 {
        PixelShader = compile ps_2_0 PSMain();
    }
}
