// UnitReplicator.h — Manages spawn/despawn of unit actors in UE5 scene
#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "TwinStateActor.h"
#include "UnitReplicator.generated.h"

UCLASS() class BATTLETWIN_API AUnitReplicator : public AActor
{
    GENERATED_BODY()
public:
    AUnitReplicator();
    virtual void Tick(float DeltaTime) override;
    UFUNCTION(BlueprintCallable) void SyncUnits(const TArray<FTwinUnit>& InUnits);
    UPROPERTY(EditAnywhere) TSubclassOf<AActor> FriendlyUnitClass;
    UPROPERTY(EditAnywhere) TSubclassOf<AActor> HostileUnitClass;
    UPROPERTY(EditAnywhere) TSubclassOf<AActor> UnknownUnitClass;
private:
    TMap<FString, AActor*> SpawnedUnits;
    AActor* SpawnUnitActor(const FTwinUnit& Unit);
    void UpdateUnitActor(AActor* Actor, const FTwinUnit& Unit);
    void DespawnStaleUnits(const TArray<FTwinUnit>& CurrentUnits);
};
