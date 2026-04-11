import React from "react";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { AlertCircle } from "lucide-react";

interface ErrorAlertProps {
  title: string;
  message: string;
  onRetry?: () => void;
}

export function ErrorAlert({ title, message, onRetry }: ErrorAlertProps) {
  return (
    <Alert variant="destructive">
      <AlertCircle className="h-4 w-4" />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>
        <p>{message}</p>
        {onRetry && (
          <Button
            variant="outline"
            size="sm"
            onClick={onRetry}
            className="mt-3 border-red-200 text-red-700 hover:bg-red-50"
          >
            Try Again
          </Button>
        )}
      </AlertDescription>
    </Alert>
  );
}
