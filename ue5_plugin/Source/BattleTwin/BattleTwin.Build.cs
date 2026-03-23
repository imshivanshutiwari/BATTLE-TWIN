// BattleTwin.Build.cs
using UnrealBuildTool;

public class BattleTwin : ModuleRules
{
    public BattleTwin(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = ModuleRules.PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new string[] { 
            "Core", "CoreUObject", "Engine", "InputCore",
            "Sockets", "Networking", "Json", "JsonUtilities",
            "Http"
        });

        PrivateDependencyModuleNames.AddRange(new string[] {
            "Slate", "SlateCore"
        });
    }
}
