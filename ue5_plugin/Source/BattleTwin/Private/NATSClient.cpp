// NATSClient.cpp
#include "NATSClient.h"
#include "Sockets.h"
#include "SocketSubsystem.h"
#include "JsonObjectConverter.h"

UNATSClient::UNATSClient() { PrimaryComponentTick.bCanEverTick = true; PrimaryComponentTick.TickInterval = 0.1f; }
void UNATSClient::BeginPlay() { Super::BeginPlay(); Connect(); }
void UNATSClient::TickComponent(float DT, ELevelTick TT, FActorComponentTickFunction* TF)
{
    Super::TickComponent(DT, TT, TF);
    // Poll for NATS messages via TCP or WebSocket bridge
}
void UNATSClient::Connect()
{
    UE_LOG(LogTemp, Log, TEXT("BATTLE-TWIN NATS: Connecting to %s"), *ServerURL);
    bConnected = true;
}
void UNATSClient::Disconnect() { bConnected = false; }
FString UNATSClient::GetLatestState() const { return LatestState; }
void UNATSClient::ProcessMessage(const FString& Subject, const FString& Data)
{
    LatestState = Data;
    Sequence++;
    OnStateUpdate.Broadcast(Data);
}
