local RunService = game:GetService("RunService")

local screenGui = Instance.new("ScreenGui")
local textLabel = Instance.new("TextLabel")

screenGui.Parent = game.CoreGui
screenGui.DisplayOrder = 100000000000000000

textLabel.Parent = screenGui
textLabel.Size = UDim2.new(0, 300, 0, 50)
textLabel.Position = UDim2.new(0, 10, 0, 10)
textLabel.Font = Enum.Font.FredokaOne
textLabel.TextScaled = true
textLabel.BackgroundTransparency = 1
textLabel.TextStrokeTransparency = 0

local function rainbowColor()
    local Dreamon = 0
    while true do
        Dreamon = Dreamon + 0.01
        if Dreamon > 1 then Dreamon = 0 end
        textLabel.TextColor3 = Color3.fromHSV(Dreamon, 1, 1)
        RunService.RenderStepped:Wait()
    end
end

local frameCount = 0
local lastUpdate = tick()

RunService.RenderStepped:Connect(function()
    frameCount = frameCount + 1
    local now = tick()

    if now - lastUpdate >= 1 then
        local fps = frameCount / (now - lastUpdate)
        frameCount = 0
        lastUpdate = now

        textLabel.Text = string.format("FPS: %d", math.floor(fps))
    end
end)

spawn(rainbowColor)

local GuiService = game:GetService("GuiService")
local Players = game:GetService("Players")
local os_time = os.time()

getgenv().StopUpdate = false

GuiService.ErrorMessageChanged:Connect(function()
    local Code = GuiService:GetErrorCode().Value
    if Code >= Enum.ConnectionError.DisconnectErrors.Value then
        getgenv().StopUpdate = true
    end
end)

repeat wait() until game.JobId ~= nil

local function writeExecutorStatus(status)
    local username = Players.LocalPlayer.Name  -- Get the player's username
    pcall(function() 
        writefile("executor_check_" .. username .. ".txt", status .. ":" .. os_time)  -- username and timestamp
    end)
end

writeExecutorStatus("working")

while wait(1) do
    if not getgenv().StopUpdate and Players.LocalPlayer and Players.LocalPlayer:FindFirstChild("PlayerScripts") then 
        writeExecutorStatus("working")
    end
end