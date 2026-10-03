FC = FC or {}

local presets = {
    clear    = {weather=0, rain=0.0, wet=0.0, fog=650, cloud=0.0},
    sunset   = {weather=0, rain=0.0, wet=0.0, fog=560, cloud=0.08, phase="sunset"},
    night    = {weather=0, rain=0.0, wet=0.0, fog=560, cloud=0.10, phase="night"},
    rain     = {weather=8, rain=0.72, wet=1.0, fog=360, cloud=0.72},
    storm    = {weather=16, rain=1.15, wet=1.0, fog=285, cloud=0.92},
    fog      = {weather=9, rain=0.0, wet=0.12, fog=185, cloud=0.66},
    postrain = {weather=4, rain=0.0, wet=0.32, fog=440, cloud=0.28}
}

local skyPalettes = {
    night  = {{18,27,43},{40,54,69}},
    dawn   = {{83,103,126},{199,151,119}},
    day    = {{74,116,164},{174,197,211}},
    sunset = {{70,83,111},{218,137,91}}
}

local function clamp(value, low, high)
    return math.max(low, math.min(high, value))
end

local function mix(a, b, t)
    return a + (b - a) * t
end

local function mixColor(a, b, t)
    return {mix(a[1],b[1],t),mix(a[2],b[2],t),mix(a[3],b[3],t)}
end

local function roundColor(c)
    return math.floor(clamp(c + 0.5, 0, 255))
end

local function getClockPhase(hour, forcedPhase)
    if forcedPhase then return forcedPhase end
    if hour >= 20 or hour < 5 then return "night" end
    if hour < 7 then return "dawn" end
    if hour >= 16 and hour < 19 then return "sunset" end
    return "day"
end

local function autoWeather(hour, dayNumber)
    -- A restrained, deterministic calendar: wet spells are occasional and
    -- followed by a long drying interval instead of permanent rain.
    if dayNumber % 11 == 7 and hour >= 2 and hour < 4 then return "storm" end
    if dayNumber % 7 == 3 and hour >= 14 and hour < 17 then return "rain" end
    if dayNumber % 7 == 3 and hour >= 17 and hour < 20 then return "postrain" end
    if dayNumber % 9 == 5 and hour >= 4 and hour < 8 then return "fog" end
    if hour >= 16 and hour < 19 then return "sunset" end
    if hour >= 20 or hour < 5 then return "night" end
    return "clear"
end

local function makeTexture(path)
    local texture = dxCreateTexture(path, "dxt1", true, "wrap")
    if texture then
        FC.loadedTextures[#FC.loadedTextures + 1] = texture
    else
        FC.log("dxCreateTexture failed: " .. path, 2)
    end
    return texture
end

local function makeShader(path, distance)
    local shader = dxCreateShader(path, 1, distance or 500, false, "object")
    if not shader then
        FC.log("dxCreateShader failed: " .. path, 2)
        return false
    end
    FC.shaderElements[#FC.shaderElements + 1] = shader
    return shader
end

function FC.clearShaders()
    for _, tile in ipairs(FC.tiles or {}) do
        for _, entry in pairs(FC.fx or {}) do
            if entry.shader and isElement(entry.shader) then
                for _, textureName in ipairs(entry.names or {}) do
                    engineRemoveShaderFromWorldTexture(entry.shader, textureName, tile.high)
                    engineRemoveShaderFromWorldTexture(entry.shader, textureName, tile.low)
                end
            end
        end
    end
    for _, shader in ipairs(FC.shaderElements or {}) do
        if isElement(shader) then destroyElement(shader) end
    end
    FC.shaderElements = {}
    FC.fx = {}
    for _, texture in ipairs(FC.loadedTextures or {}) do
        if isElement(texture) and getElementType(texture) == "texture" then
            destroyElement(texture)
        end
    end
    FC.loadedTextures = {}
end

function FC.createShaders()
    if FC.fx and next(FC.fx) then return true end
    FC.shaderElements = FC.shaderElements or {}
    FC.loadedTextures = FC.loadedTextures or {}
    FC.fx = {}

    local asphaltNormal = makeTexture("textures/fc_asphalt_n.dds")
    local asphaltRough = makeTexture("textures/fc_asphalt_r.dds")
    local asphaltMask = makeTexture("textures/fc_asphalt_m.dds")
    local waterNormal = makeTexture("textures/fc_water_n.dds")
    local weatherNoise = makeTexture("textures/weather_noise.dds")

    local road = makeShader("shaders/wet_road.fx", 650)
    if road then
        if asphaltNormal then dxSetShaderValue(road,"gNormalTexture",asphaltNormal) end
        if asphaltRough then dxSetShaderValue(road,"gRoughnessTexture",asphaltRough) end
        if asphaltMask then dxSetShaderValue(road,"gPuddleTexture",asphaltMask) end
        FC.fx.road={shader=road,names={"fc_asphalt"},kind="road"}
    end

    local water = makeShader("shaders/water.fx", 850)
    if water then
        if waterNormal then dxSetShaderValue(water,"gNormalTexture",waterNormal) end
        if weatherNoise then dxSetShaderValue(water,"gNoiseTexture",weatherNoise) end
        FC.fx.water={shader=water,names={"fc_water"},kind="water"}
    end

    local window = makeShader("shaders/window_light.fx", 700)
    if window then
        dxSetShaderValue(window,"gWindowTint",1.0,0.73,0.46)
        dxSetShaderValue(window,"gEmission",0.34)
        dxSetShaderValue(window,"gDayScale",0.48)
        FC.fx.windowWarm={shader=window,names={"fc_winwarm"},kind="window"}
    end
    local windowCool = makeShader("shaders/window_light.fx", 700)
    if windowCool then
        dxSetShaderValue(windowCool,"gWindowTint",0.62,0.79,1.0)
        dxSetShaderValue(windowCool,"gEmission",0.23)
        dxSetShaderValue(windowCool,"gDayScale",0.62)
        FC.fx.windowCool={shader=windowCool,names={"fc_wincool"},kind="window"}
    end
    local darkWindow = makeShader("shaders/window_light.fx", 700)
    if darkWindow then
        dxSetShaderValue(darkWindow,"gWindowTint",0.72,0.78,0.82)
        dxSetShaderValue(darkWindow,"gEmission",0.035)
        dxSetShaderValue(darkWindow,"gDayScale",0.42)
        FC.fx.windowDark={shader=darkWindow,names={"fc_windark"},kind="window"}
    end

    local glass = makeShader("shaders/glass_tint.fx", 650)
    if glass then FC.fx.glass={shader=glass,names={"fc_glass"},kind="glass"} end
    return true
end

function FC.applyShadersToTile(tile)
    for _, entry in pairs(FC.fx or {}) do
        if entry.shader and isElement(entry.shader) then
            for _, textureName in ipairs(entry.names or {}) do
                engineApplyShaderToWorldTexture(entry.shader,textureName,tile.high)
                engineApplyShaderToWorldTexture(entry.shader,textureName,tile.low)
            end
        end
    end
end

function FC.applyQuality(name)
    if name ~= "low" and name ~= "medium" and name ~= "high" then
        name="high"
    end
    FC.quality=name
    local tuning={
        low={far=360,highLOD=120,lowLOD=360,lightBudget=6,lightDistance=150,shaders=false},
        medium={far=520,highLOD=165,lowLOD=520,lightBudget=14,lightDistance=220,shaders=true},
        high={far=720,highLOD=185,lowLOD=720,lightBudget=24,lightDistance=290,shaders=true}
    }
    FC.qualitySettings=tuning[name]
    setFarClipDistance(FC.qualitySettings.far)
    for _, tile in ipairs(FC.tiles or {}) do
        local hi=tile.record.highModelID
        local lo=tile.record.lowModelID
        if hi then engineSetModelLODDistance(hi,FC.qualitySettings.highLOD,true) end
        if lo then engineSetModelLODDistance(lo,FC.qualitySettings.lowLOD,true) end
    end
    if FC.qualitySettings.shaders then
        if not FC.fx or not next(FC.fx) then FC.createShaders() end
        if FC.applyShadersToTile then
            for _, tile in ipairs(FC.tiles or {}) do FC.applyShadersToTile(tile) end
        end
    elseif FC.fx and next(FC.fx) then
        FC.clearShaders()
    end
    FC.log("quality preset: " .. name)
end

local function phasePalette(hour, phase, cloud)
    local palette=skyPalettes[phase] or skyPalettes.day
    local top,bottom={palette[1][1],palette[1][2],palette[1][3]},
                     {palette[2][1],palette[2][2],palette[2][3]}
    local grayTop={109,119,128};local grayBottom={157,164,165}
    top=mixColor(top,grayTop,cloud*.58)
    bottom=mixColor(bottom,grayBottom,cloud*.52)
    -- A low sun leaves a warm band even in the clear dawn/sunset phases.
    if phase=="sunset" or phase=="dawn" then
        bottom=mixColor(bottom,{220,151,112},phase=="sunset" and .34 or .22)
    end
    return top,bottom
end

local function updateDayCounter(hour, minute)
    local total=hour*60+minute
    if FC.lastMinute and total < FC.lastMinute-720 then
        FC.dayNumber=(FC.dayNumber or 0)+1
    end
    FC.lastMinute=total
end

local function chooseProfile(hour, minute)
    updateDayCounter(hour,minute)
    local selected=FC.forcedWeather
    if not selected or selected=="auto" then
        selected=autoWeather(hour+minute/60,FC.dayNumber or 0)
    end
    return selected,presets[selected] or presets.clear
end

local function updateWorldEnvironment(dt)
    local h,m=getTime()
    local selected,profile=chooseProfile(h,m)
    if selected~=FC.activePreset then
        FC.activePreset=selected
        setWeather(profile.weather)
        FC.targetWetness=profile.wet
        FC.targetRain=profile.rain
        FC.targetFog=profile.fog
        FC.targetCloud=profile.cloud
        FC.lightningAt=profile.weather==16 and (getTickCount()+math.random(55000,150000)) or nil
        FC.log("weather phase: " .. selected)
    end
    local phase=getClockPhase(h,profile.phase)
    local hour=h+m/60
    local nightTarget
    if phase=="night" then
        nightTarget=1.0
    elseif phase=="sunset" then
        nightTarget=0.22
    elseif phase=="dawn" then
        nightTarget=0.12
    else
        nightTarget=0.0
    end
    FC.night=mix(FC.night or 0,nightTarget,1-math.exp(-dt/24000))
    local wetTau=(FC.targetWetness or 0)>(FC.wetness or 0) and 28000 or 240000
    FC.wetness=mix(FC.wetness or 0,FC.targetWetness or 0,1-math.exp(-dt/wetTau))
    FC.rain=mix(FC.rain or 0,FC.targetRain or 0,1-math.exp(-dt/18000))
    FC.cloud=mix(FC.cloud or 0,FC.targetCloud or 0,1-math.exp(-dt/30000))
    FC.fog=mix(FC.fog or 600,FC.targetFog or 600,1-math.exp(-dt/40000))

    local top,bottom=phasePalette(hour,phase,FC.cloud)
    FC.skyTop=FC.skyTop or top
    FC.skyBottom=FC.skyBottom or bottom
    FC.skyTop=mixColor(FC.skyTop,top,1-math.exp(-dt/30000))
    FC.skyBottom=mixColor(FC.skyBottom,bottom,1-math.exp(-dt/30000))

    local tick=getTickCount()
    if not FC.lastWorldUpdate or tick-FC.lastWorldUpdate>650 then
        FC.lastWorldUpdate=tick
        setSkyGradient(roundColor(FC.skyTop[1]),roundColor(FC.skyTop[2]),roundColor(FC.skyTop[3]),
                       roundColor(FC.skyBottom[1]),roundColor(FC.skyBottom[2]),roundColor(FC.skyBottom[3]))
        local warmth=phase=="sunset" and .12 or (phase=="dawn" and .07 or 0)
        local sunR=roundColor(mix(210,255,warmth+FC.night*.02))
        local sunG=roundColor(mix(219,193,warmth+FC.night*.35))
        local sunB=roundColor(mix(226,160,warmth+FC.night*.55))
        setSunColor(sunR,sunG,sunB,sunR,sunG,sunB)
        setSunSize(FC.night>.7 and 0 or 1)
        setFogDistance(clamp(FC.fog,150,800))
        setRainLevel(clamp(FC.rain,0,2.0))
        local wind=(selected=="storm") and 0.65 or (selected=="rain" and 0.28 or 0.08)
        setWindVelocity(wind,wind*.37,0)
        for _,entry in pairs(FC.fx or {}) do
            if entry.shader and isElement(entry.shader) then
                if entry.kind=="road" then
                    dxSetShaderValue(entry.shader,"gWetness",FC.wetness)
                    dxSetShaderValue(entry.shader,"gWorldTime",tick/1000)
                elseif entry.kind=="water" then
                    dxSetShaderValue(entry.shader,"gRainAmount",FC.rain)
                    dxSetShaderValue(entry.shader,"gWorldTime",tick/1000)
                    dxSetShaderValue(entry.shader,"gSkyTint",0.55+FC.cloud*.17,0.67+FC.cloud*.12,0.78+FC.cloud*.08)
                elseif entry.kind=="window" then
                    dxSetShaderValue(entry.shader,"gNight",FC.night)
                elseif entry.kind=="glass" then
                    dxSetShaderValue(entry.shader,"gNight",FC.night)
                    dxSetShaderValue(entry.shader,"gSkyTint",0.62+FC.cloud*.12,0.74+FC.cloud*.10,0.82+FC.cloud*.08)
                end
            end
        end
    end
    if FC.updateStreetLights then FC.updateStreetLights(tick) end
    if FC.updateLightning then FC.updateLightning(tick,selected) end
end

function FC.startEnvironment()
    if not FC.runtime then return end
    FC.dayNumber=0
    FC.forcedWeather="auto"
    FC.targetWetness=0;FC.targetRain=0;FC.targetFog=600;FC.targetCloud=0
    FC.lastMinute=nil
    FC.originalMinuteDuration=getMinuteDuration()
    setMinuteDuration(1800) -- about 43 minutes per in-game day, for an inspectable day/night cycle
    math.randomseed(getTickCount()+getRealTime().timestamp)
    FC.preRenderHandler=function(msSinceLastFrame)
        updateWorldEnvironment(clamp(tonumber(msSinceLastFrame) or 16,0,250))
    end
    addEventHandler("onClientPreRender",root,FC.preRenderHandler)
    FC.log("day/night, native weather, wetness and fog controller active")
end

function FC.stopEnvironment()
    if FC.preRenderHandler then
        removeEventHandler("onClientPreRender",root,FC.preRenderHandler)
        FC.preRenderHandler=nil
    end
    for _,entry in pairs(FC.runtimeLights or {}) do
        if isElement(entry) then destroyElement(entry) end
    end
    FC.runtimeLights={}
    FC.clearShaders()
    resetRainLevel()
    resetWeather()
    resetFarClipDistance()
    resetFogDistance()
    resetSkyGradient()
    resetSunColor()
    resetSunSize()
    resetWindVelocity()
    if FC.originalMinuteDuration then
        setMinuteDuration(FC.originalMinuteDuration)
        FC.originalMinuteDuration=nil
    end
end

function FC.forceWeather(name)
    if name=="auto" then
        FC.forcedWeather="auto"
        FC.activePreset=nil
        FC.log("weather schedule returned to automatic mode")
        return true
    end
    if not presets[name] then return false end
    FC.forcedWeather=name
    FC.activePreset=nil
    return true
end

function FC.updateStreetLights(tick)
    if not FC.runtime or not FC.qualitySettings or tick-(FC.lastLightUpdate or 0)<1200 then return end
    FC.lastLightUpdate=tick
    local night=FC.night or 0
    local budget=FC.qualitySettings.lightBudget
    local x,y,z=getElementPosition(localPlayer)
    local candidates={}
    for _,light in ipairs(FC.runtime.lights or {}) do
        local dx,dy=light.worldX-x,light.worldY-y
        local d2=dx*dx+dy*dy
        if d2<FC.qualitySettings.lightDistance^2 then
            candidates[#candidates+1]={record=light,d2=d2}
        end
    end
    table.sort(candidates,function(a,b) return a.d2<b.d2 end)
    local wanted={}
    if night>.16 then
        for i=1,math.min(#candidates,budget) do wanted[candidates[i].record.id]=candidates[i].record end
    end
    FC.runtimeLights=FC.runtimeLights or {}
    for id,element in pairs(FC.runtimeLights) do
        if not wanted[id] or not isElement(element) then
            if isElement(element) then destroyElement(element) end
            FC.runtimeLights[id]=nil
        end
    end
    for id,record in pairs(wanted) do
        local red,green,blue=unpack(record.color or {235,214,171})
        local intensity=(record.intensity or .4)*night
        local r=math.floor(clamp(red*intensity,0,255))
        local g=math.floor(clamp(green*intensity,0,255))
        local b=math.floor(clamp(blue*intensity,0,255))
        local light=FC.runtimeLights[id]
        if not isElement(light) then
            light=createLight(0,record.worldX,record.worldY,record.worldZ,
                              math.min(record.range or 26,32),r,g,b)
            if light then FC.runtimeLights[id]=light end
        elseif light then
            setLightColor(light,r,g,b)
            setLightRadius(light,math.min(record.range or 26,32))
        end
    end
end

function FC.updateLightning(tick,activePreset)
    if activePreset~="storm" then return end
    -- GTA's native storm weather owns the visible lightning; this resource only
    -- schedules sparse generated thunder cues instead of drawing a fake bolt.
    if not FC.lightningAt or tick>=FC.lightningAt then
        FC.lightningAt=tick+math.random(90000,240000)
        if FC.runtime and #FC.runtime.thunderFiles>0 then
            local path=FC.runtime.thunderFiles[math.random(#FC.runtime.thunderFiles)]
            local px=FC.runtime.originX+math.random(-160,160)
            local py=FC.runtime.originY+math.random(-160,160)
            local sound=playSound3D(path,px,py,90,false)
            if sound then
                setSoundVolume(sound,.62)
                setSoundMinDistance(sound,80)
                setSoundMaxDistance(sound,1200)
            end
        end
    end
end
