local function usage()
    outputChatBox("/fcweather <auto|clear|sunset|night|rain|storm|fog|postrain>",255,220,160)
    outputChatBox("/fcquality <low|medium|high> | /fcenv | /cityspawn | /citydrive",255,220,160)
end

addCommandHandler("fcweather",function(_,name)
    if not name then usage(); return end
    name=name:lower()
    if not FC.forceWeather or not FC.forceWeather(name) then
        outputChatBox("Unknown weather preset. Use /fcweather auto|clear|sunset|night|rain|storm|fog|postrain",255,100,100)
        return
    end
    outputChatBox("Northpoint weather: " .. name,205,220,235)
end)

addCommandHandler("fcquality",function(_,name)
    name=name and name:lower() or ""
    if name~="low" and name~="medium" and name~="high" then
        outputChatBox("Usage: /fcquality low|medium|high",255,220,160)
        return
    end
    if FC.applyQuality then FC.applyQuality(name) end
end)

addCommandHandler("fcenv",function()
    local h,m=getTime()
    outputChatBox(string.format("Northpoint Harbor | %02d:%02d | weather %s | wetness %.2f | quality %s",
        h,m,tostring(FC.activePreset or "loading"),FC.wetness or 0,FC.quality or "high"),190,220,235)
end)

addCommandHandler("cityspawn",function()
    triggerServerEvent("freecity:spawn",resourceRoot,false)
end)

addCommandHandler("citydrive",function()
    triggerServerEvent("freecity:spawn",resourceRoot,true)
end)

addCommandHandler("fchelp",usage)
