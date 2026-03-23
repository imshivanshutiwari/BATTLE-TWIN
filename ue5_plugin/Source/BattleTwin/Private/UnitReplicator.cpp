// UnitReplicator.cpp — Manages spawn/despawn of units in the UE5 scene
#include "UnitReplicator.h"

AUnitReplicator::AUnitReplicator() { PrimaryActorTick.bCanEverTick = true; }
void AUnitReplicator::Tick(float DeltaTime) { Super::Tick(DeltaTime); }

void AUnitReplicator::SyncUnits(const TArray<FTwinUnit>& InUnits)
{
    DespawnStaleUnits(InUnits);
    for (const auto& U : InUnits)
    {
        if (AActor** Existing = SpawnedUnits.Find(U.UID))
        {
            UpdateUnitActor(*Existing, U);
        }
        else
        {
            AActor* NewActor = SpawnUnitActor(U);
            if (NewActor)
                SpawnedUnits.Add(U.UID, NewActor);
        }
    }
}

AActor* AUnitReplicator::SpawnUnitActor(const FTwinUnit& Unit)
{
    UClass* ClassToSpawn = nullptr;
    if (Unit.Affiliation == TEXT("FRIENDLY") && FriendlyUnitClass)
        ClassToSpawn = FriendlyUnitClass;
    else if (Unit.Affiliation == TEXT("HOSTILE") && HostileUnitClass)
        ClassToSpawn = HostileUnitClass;
    else if (UnknownUnitClass)
        ClassToSpawn = UnknownUnitClass;
    if (!ClassToSpawn) return nullptr;
    FActorSpawnParameters Params;
    Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    AActor* Actor = GetWorld()->SpawnActor<AActor>(ClassToSpawn, FTransform(Unit.Position), Params);
    return Actor;
}

void AUnitReplicator::UpdateUnitActor(AActor* Actor, const FTwinUnit& Unit)
{
    if (!Actor) return;
    Actor->SetActorLocation(FMath::VInterpTo(Actor->GetActorLocation(), Unit.Position, GetWorld()->GetDeltaSeconds(), 5.0f));
    Actor->SetActorRotation(FRotator(0, Unit.Heading, 0));
}

void AUnitReplicator::DespawnStaleUnits(const TArray<FTwinUnit>& CurrentUnits)
{
    TSet<FString> CurrentUIDs;
    for (const auto& U : CurrentUnits) CurrentUIDs.Add(U.UID);
    TArray<FString> ToRemove;
    for (const auto& Pair : SpawnedUnits)
    {
        if (!CurrentUIDs.Contains(Pair.Key))
        {
            if (Pair.Value) Pair.Value->Destroy();
            ToRemove.Add(Pair.Key);
        }
    }
    for (const auto& Key : ToRemove) SpawnedUnits.Remove(Key);
}
