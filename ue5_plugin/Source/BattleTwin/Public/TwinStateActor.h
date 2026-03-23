// TwinStateActor.h — Receives and applies battlefield state updates
#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "TwinStateActor.generated.h"

USTRUCT(BlueprintType) struct FTwinUnit { GENERATED_BODY()
    UPROPERTY(BlueprintReadOnly) FString UID;
    UPROPERTY(BlueprintReadOnly) FString Callsign;
    UPROPERTY(BlueprintReadOnly) FVector Position;
    UPROPERTY(BlueprintReadOnly) float Heading;
    UPROPERTY(BlueprintReadOnly) float Speed;
    UPROPERTY(BlueprintReadOnly) float Strength;
    UPROPERTY(BlueprintReadOnly) float ThreatLevel;
    UPROPERTY(BlueprintReadOnly) FString Affiliation;
};

UCLASS() class BATTLETWIN_API ATwinStateActor : public AActor
{
    GENERATED_BODY()
public:
    ATwinStateActor();
    virtual void Tick(float DeltaTime) override;
    UFUNCTION(BlueprintCallable) void UpdateFromJSON(const FString& JsonState);
    UPROPERTY(BlueprintReadOnly) TArray<FTwinUnit> Units;
    UPROPERTY(BlueprintReadOnly) TArray<FTwinUnit> Contacts;
    UPROPERTY(BlueprintReadOnly) int32 StateSequence = 0;
private:
    void ParseUnits(const TSharedPtr<FJsonObject>& Root);
    void InterpolatePositions(float DeltaTime);
    TMap<FString, FVector> TargetPositions;
};
