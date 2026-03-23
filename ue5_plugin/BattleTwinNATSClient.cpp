// BattleTwinNATSClient.cpp - UE5 NATS JetStream client implementation
#include "BattleTwinNATSClient.h"
#include "JsonObjectConverter.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

ABattleTwinNATSClient::ABattleTwinNATSClient()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickInterval = 0.1f; // 10 Hz
}

void ABattleTwinNATSClient::BeginPlay()
{
    Super::BeginPlay();
    Connect();
}

void ABattleTwinNATSClient::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
    // Poll NATS for state updates would go here
    // Using cnats library or WebSocket bridge
}

void ABattleTwinNATSClient::Connect()
{
    UE_LOG(LogTemp, Log, TEXT("BATTLE-TWIN: Connecting to NATS at %s"), *NATSServerURL);
    // NATS connection via cnats or WebSocket bridge
    bConnected = true;
}

void ABattleTwinNATSClient::Disconnect()
{
    bConnected = false;
    UE_LOG(LogTemp, Log, TEXT("BATTLE-TWIN: Disconnected from NATS"));
}

bool ABattleTwinNATSClient::IsConnected() const { return bConnected; }

void ABattleTwinNATSClient::ProcessStateUpdate(const FString& JsonPayload)
{
    TSharedPtr<FJsonObject> JsonObj;
    TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonPayload);
    if (!FJsonSerializer::Deserialize(Reader, JsonObj)) return;
    NATSSequence = JsonObj->GetIntegerField(TEXT("seq"));
    ParseUnits(JsonObj);
}

void ABattleTwinNATSClient::ParseUnits(const TSharedPtr<FJsonObject>& JsonObj)
{
    FriendlyUnits.Empty();
    HostileContacts.Empty();
    const TArray<TSharedPtr<FJsonValue>>* Units;
    if (JsonObj->TryGetArrayField(TEXT("units"), Units))
    {
        for (const auto& Val : *Units)
        {
            auto UnitObj = Val->AsObject();
            FBattlefieldUnit Unit;
            Unit.UID = UnitObj->GetStringField(TEXT("uid"));
            Unit.Affiliation = UnitObj->GetStringField(TEXT("aff"));
            Unit.Position = FVector(
                UnitObj->GetNumberField(TEXT("lat")),
                UnitObj->GetNumberField(TEXT("lon")),
                UnitObj->GetNumberField(TEXT("alt")));
            Unit.Heading = UnitObj->GetNumberField(TEXT("hdg"));
            Unit.Speed = UnitObj->GetNumberField(TEXT("spd"));
            Unit.Strength = UnitObj->GetNumberField(TEXT("str"));
            Unit.ThreatLevel = UnitObj->GetNumberField(TEXT("thr"));
            if (Unit.Affiliation == TEXT("FRIENDLY"))
                FriendlyUnits.Add(Unit);
            else
                HostileContacts.Add(Unit);
        }
    }
}
