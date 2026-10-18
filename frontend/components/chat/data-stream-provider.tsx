"use client";

import type { DataUIPart } from "ai";
import type React from "react";
import { createContext, useContext, useMemo, useState } from "react";
import type { RagStage } from "@/lib/rag/types";
import type { CustomUIDataTypes, WaitingStatusData } from "@/lib/types";

type DataStreamContextValue = {
  dataStream: DataUIPart<CustomUIDataTypes>[];
  setDataStream: React.Dispatch<
    React.SetStateAction<DataUIPart<CustomUIDataTypes>[]>
  >;
  waitingStatus: WaitingStatusData | undefined;
  setWaitingStatus: React.Dispatch<
    React.SetStateAction<WaitingStatusData | undefined>
  >;
  /** Pipeline stage the backend is currently working on (transient). */
  ragStage: RagStage | undefined;
  setRagStage: React.Dispatch<React.SetStateAction<RagStage | undefined>>;
};

const DataStreamContext = createContext<DataStreamContextValue | null>(null);

export function DataStreamProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [dataStream, setDataStream] = useState<DataUIPart<CustomUIDataTypes>[]>(
    []
  );
  const [waitingStatus, setWaitingStatus] = useState<WaitingStatusData>();
  const [ragStage, setRagStage] = useState<RagStage>();

  const value = useMemo(
    () => ({
      dataStream,
      ragStage,
      setDataStream,
      setRagStage,
      setWaitingStatus,
      waitingStatus,
    }),
    [dataStream, ragStage, waitingStatus]
  );

  return (
    <DataStreamContext.Provider value={value}>
      {children}
    </DataStreamContext.Provider>
  );
}

export function useDataStream() {
  const context = useContext(DataStreamContext);
  if (!context) {
    throw new Error("useDataStream must be used within a DataStreamProvider");
  }
  return context;
}
