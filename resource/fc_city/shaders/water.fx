// Animated local normal/specular water; the DX9 path has no screen-space reflections.
texture gTexture;
texture gNormalTexture;
texture gNoiseTexture;
float gWorldTime = 0.0;
float gRainAmount = 0.0;
float3 gSkyTint = float3(0.72, 0.79, 0.84);

sampler BaseSampler = sampler_state {
    Texture = <gTexture>;
    MinFilter = Linear; MagFilter = Linear; MipFilter = Linear;
    AddressU = Wrap; AddressV = Wrap;
};
sampler NormalSampler = sampler_state {
    Texture = <gNormalTexture>;
    MinFilter = Linear; MagFilter = Linear; MipFilter = Linear;
    AddressU = Wrap; AddressV = Wrap;
};
sampler NoiseSampler = sampler_state {
    Texture = <gNoiseTexture>;
    MinFilter = Linear; MagFilter = Linear; MipFilter = Linear;
    AddressU = Wrap; AddressV = Wrap;
};

float4 PSMain(float2 uv : TEXCOORD0, float4 vertexColor : COLOR0) : COLOR0 {
    float2 driftA = uv * 1.45 + float2(gWorldTime * 0.006, -gWorldTime * 0.003);
    float2 driftB = uv * 0.73 + float2(-gWorldTime * 0.002, gWorldTime * 0.004);
    float3 nA = tex2D(NormalSampler, driftA).xyz * 2.0 - 1.0;
    float3 nB = tex2D(NormalSampler, driftB).zyx * 2.0 - 1.0;
    float noise = tex2D(NoiseSampler, driftB).r;
    float3 normal = normalize(float3(nA.xy * 0.6 + nB.xy * 0.4, 1.0));
    float3 lightDir = normalize(float3(-0.28, -0.38, 0.88));
    float3 halfVector = normalize(lightDir + float3(0.0, 0.0, 1.0));
    float specular = pow(saturate(dot(normal, halfVector)), 18.0) * (0.06 + 0.14 * gRainAmount);
    float3 base = tex2D(BaseSampler, uv + (noise - 0.5) * 0.008).rgb;
    float3 color = lerp(base, base * gSkyTint, 0.35) + specular;
    return float4(saturate(color * vertexColor.rgb), vertexColor.a);
}

technique WaterSurface {
    pass P0 {
        PixelShader = compile ps_2_0 PSMain();
    }
}
