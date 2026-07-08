import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { deleteAttempt, deleteHistory, fetchHistory } from "../lib/api";

export function useAssessmentHistory() {
  return useQuery({
    queryKey: ["assessment-history"],
    queryFn: fetchHistory,
  });
}

export function useDeleteAttempt() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteAttempt,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["assessment-history"] });
    },
  });
}

export function useDeleteHistory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteHistory,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["assessment-history"] });
    },
  });
}
