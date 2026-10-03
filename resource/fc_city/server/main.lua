local CITY = {spawn={x=2600,y=-140,z=5,rotation=0}, lastSpawn={}}

local function loadCityData()
    local file=fileOpen("data/city_runtime.json")
    if not file then
        outputDebugString("[Northpoint Harbor] runtime JSON missing; run tools/build_city.py",1)
        return
    end
    local raw=fileRead(file,fileGetSize(file));fileClose(file)
    local data=raw and fromJSON(raw)
    if type(data)=="table" and type(data.spawn)=="table" then
        CITY.spawn=data.spawn
    end
end

addEventHandler("onResourceStart",resourceRoot,loadCityData)
addEvent("freecity:spawn",true)
addEventHandler("freecity:spawn",resourceRoot,function(withVehicle)
    local player=client
    if not player or not isElement(player) or getElementType(player)~="player" then return end
    local now=getTickCount()
    local previous=CITY.lastSpawn[player]
    if previous and now-previous<1500 then return end
    CITY.lastSpawn[player]=now
    local point=CITY.spawn
    local x,y,z=tonumber(point.x),tonumber(point.y),tonumber(point.z)
    local rotation=tonumber(point.rotation) or 0
    if not x or not y or not z then return end
    local wantsVehicle=(withVehicle==true)
    setElementInterior(player,0)
    setElementDimension(player,0)
    if isPedDead(player) then
        spawnPlayer(player,x,y,z,rotation,getElementModel(player),0,0)
        fadeCamera(player,true)
        setCameraTarget(player,player)
    else
        local occupied=getPedOccupiedVehicle(player)
        if isElement(occupied) then
            setElementPosition(occupied,x,y,z+1.0)
            setElementRotation(occupied,0,0,rotation)
        else
            setElementPosition(player,x,y,z)
            setElementRotation(player,0,0,rotation)
        end
    end
    if wantsVehicle and not isPedDead(player) then
        local vehicle=getPedOccupiedVehicle(player)
        if not isElement(vehicle) then
            vehicle=createVehicle(560,x+3.0,y,z+1.0,0,0,rotation)
            if vehicle then
                setElementInterior(vehicle,0)
                setElementDimension(vehicle,0)
                setVehicleColor(vehicle,54,62,66,170,178,173)
                setVehicleDamageProof(vehicle,true)
                setVehicleEngineState(vehicle,true)
                warpPedIntoVehicle(player,vehicle)
            end
        end
    end
    outputChatBox("Northpoint Harbor loaded. Try /fcweather and /fcquality.",player,175,215,230)
end)

addEventHandler("onPlayerQuit",root,function()
    CITY.lastSpawn[source]=nil
end)
