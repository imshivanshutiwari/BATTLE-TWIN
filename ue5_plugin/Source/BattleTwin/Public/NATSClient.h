// NATSClient.h — NATS JetStream client for UE5
#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "NATSClient.generated.h"

UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class BATTLETWIN_API UNATSClient : public UActorComponent
{
    GENERATED_BODY()
public:
    UNATSClient();
    virtual void BeginPlay() override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

    UPROPERTY(EditAnywhere, Category="NATS") FString ServerURL = TEXT("nats://localhost:4222");
    UPROPERTY(EditAnywhere, Category="NATS") FString StreamName = TEXT("BATTLEFIELD");
    UPROPERTY(BlueprintReadOnly, Category="NATS") bool bConnected = false;
    UPROPERTY(BlueprintReadOnly, Category="NATS") int32 Sequence = 0;

    UFUNCTION(BlueprintCallable) void Connect();
    UFUNCTION(BlueprintCallable) void Disconnect();
    UFUNCTION(BlueprintCallable) FString GetLatestState() const;

    DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnStateUpdate, const FString&, JsonState);
    UPROPERTY(BlueprintAssignable) FOnStateUpdate OnStateUpdate;
private:
    FString LatestState;
    void ProcessMessage(const FString& Subject, const FString& Data);
};
