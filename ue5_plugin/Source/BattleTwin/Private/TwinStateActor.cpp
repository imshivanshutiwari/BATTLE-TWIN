// TwinStateActor.cpp
#include "TwinStateActor.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

ATwinStateActor::ATwinStateActor() { PrimaryActorTick.bCanEverTick = true; PrimaryActorTick.TickInterval = 0.1f; }
void ATwinStateActor::Tick(float DeltaTime) { Super::Tick(DeltaTime); InterpolatePositions(DeltaTime); }

void ATwinStateActor::UpdateFromJSON(const FString& JsonState)
{
    TSharedPtr<FJsonObject> Root;
    TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonState);
    if (!FJsonSerializer::Deserialize(Reader, Root)) return;
    StateSequence = Root->GetIntegerField(TEXT("seq"));
    ParseUnits(Root);
}

void ATwinStateActor::ParseUnits(const TSharedPtr<FJsonObject>& Root)
{
    Units.Empty(); Contacts.Empty();
    const TArray<TSharedPtr<FJsonValue>>* UnitsArr;
    if (Root->TryGetArrayField(TEXT("units"), UnitsArr))
    {
        for (const auto& V : *UnitsArr)
        {
            auto O = V->AsObject();
            FTwinUnit U;
            U.UID = O->GetStringField(TEXT("uid"));
            U.Callsign = O->GetStringField(TEXT("callsign"));
            U.Position = FVector(O->GetNumberField(TEXT("lat")), O->GetNumberField(TEXT("lon")), O->GetNumberField(TEXT("alt")));
            U.Heading = O->GetNumberField(TEXT("hdg"));
            U.Speed = O->GetNumberField(TEXT("spd"));
            U.Strength = O->GetNumberField(TEXT("str"));
            U.ThreatLevel = O->GetNumberField(TEXT("thr"));
            U.Affiliation = O->GetStringField(TEXT("aff"));
            TargetPositions.Add(U.UID, U.Position);
            if (U.Affiliation == TEXT("FRIENDLY")) Units.Add(U); else Contacts.Add(U);
        }
    }
}

void ATwinStateActor::InterpolatePositions(float DeltaTime)
{
    // Smooth position updates via lerp
    for (auto& U : Units)
    {
        if (FVector* Target = TargetPositions.Find(U.UID))
            U.Position = FMath::VInterpTo(U.Position, *Target, DeltaTime, 5.0f);
    }
}
