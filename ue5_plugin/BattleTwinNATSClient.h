// BattleTwinNATSClient.h - UE5 NATS JetStream client
// Connects to BATTLE-TWIN Python backend via NATS
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BattleTwinNATSClient.generated.h"

USTRUCT(BlueprintType)
struct FBattlefieldUnit
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly) FString UID;
    UPROPERTY(BlueprintReadOnly) FString Callsign;
    UPROPERTY(BlueprintReadOnly) FString UnitType;
    UPROPERTY(BlueprintReadOnly) FVector Position;
    UPROPERTY(BlueprintReadOnly) float Heading;
    UPROPERTY(BlueprintReadOnly) float Speed;
    UPROPERTY(BlueprintReadOnly) float Strength;
    UPROPERTY(BlueprintReadOnly) float ThreatLevel;
    UPROPERTY(BlueprintReadOnly) FString Affiliation;
};

UCLASS()
class BATTLETWIN_API ABattleTwinNATSClient : public AActor
{
    GENERATED_BODY()

public:
    ABattleTwinNATSClient();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaTime) override;

    UPROPERTY(EditAnywhere, Category="NATS")
    FString NATSServerURL = TEXT("nats://localhost:4222");

    UPROPERTY(EditAnywhere, Category="NATS")
    FString StreamName = TEXT("BATTLEFIELD");

    UPROPERTY(BlueprintReadOnly, Category="State")
    TArray<FBattlefieldUnit> FriendlyUnits;

    UPROPERTY(BlueprintReadOnly, Category="State")
    TArray<FBattlefieldUnit> HostileContacts;

    UPROPERTY(BlueprintReadOnly, Category="State")
    int32 NATSSequence = 0;

    UFUNCTION(BlueprintCallable, Category="NATS")
    void Connect();

    UFUNCTION(BlueprintCallable, Category="NATS")
    void Disconnect();

    UFUNCTION(BlueprintCallable, Category="NATS")
    bool IsConnected() const;

private:
    void ProcessStateUpdate(const FString& JsonPayload);
    void ParseUnits(const TSharedPtr<FJsonObject>& JsonObj);
    bool bConnected = false;
};
