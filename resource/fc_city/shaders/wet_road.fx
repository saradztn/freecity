// D3D9-compatible local wet-surface approximation; deliberately not SSR.
texture gTexture;
texture gNormalTexture;
texture gRoughnessTexture;
texture gPuddleTexture;
float gWetness = 0.0;
float gWorldTime = 0.0;
float3 gLightDir = float3(-0.28, -0.36, 0.89);
float3 gWetTint = float3(0.82, 0.86, 0.88);

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
sampler RoughnessSampler = sampler_state {
    Texture = <gRoughnessTexture>;
    MinFilter = Linear; MagFilter = Linear; MipFilter = Linear;
    AddressU = Wrap; AddressV = Wrap;
};
sampler PuddleSampler = sampler_state {
    Texture = <gPuddleTexture>;
    MinFilter = Linear; MagFilter = Linear; MipFilter = Linear;
    AddressU = Wrap; AddressV = Wrap;
};

float4 PSMain(float2 uv : TEXCOORD0, float4 vertexColor : COLOR0) : COLOR0 {
    float4 base = tex2D(BaseSampler, uv) * vertexColor;
    float3 tangentNormal = normalize(tex2D(NormalSampler, uv).xyz * 2.0 - 1.0);
    float rough = tex2D(RoughnessSampler, uv).r;
    float puddleMask = tex2D(PuddleSampler, uv).r;
    float wet = saturate(gWetness * (0.28 + puddleMask * 1.35));
    float3 lightDir = normalize(gLightDir);
    float3 viewApprox = float3(0.0, 0.0, 1.0);
    float3 halfVector = normalize(lightDir + viewApprox);
    float exponent = lerp(5.0, 24.0, saturate((1.0 - rough) * 0.65 + wet * 0.55));
    float highlight = pow(saturate(dot(tangentNormal, halfVector)), exponent);
    float slowGlint = 0.65 + 0.35 * sin(uv.x * 4.4 + uv.y * 0.7 + gWorldTime * 0.035);
    float puddleSheen = highlight * wet * (0.035 + 0.13 * puddleMask) * slowGlint;
    float3 diffuse = lerp(base.rgb, base.rgb * gWetTint, wet * 0.19);
    return float4(saturate(diffuse + puddleSheen), base.a);
}

technique WetAsphalt {
    pass P0 {
        PixelShader = compile ps_2_0 PSMain();
    }
}
