"""Server-side calls to Groq and Pinata, so their keys never reach the browser.

The frontend used to call both services directly with VITE_GROQ_API_KEY / VITE_PINATA_JWT_TOKEN, which Vite builds
into the public JavaScript bundle where anyone can read them. These endpoints make the same calls with keys read from
the server's environment (GROQ_API_KEY, PINATA_JWT), and only for signed-in users.
"""
import os

import requests
from django.conf import settings
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
PINATA_URL = "https://uploads.pinata.cloud/v3/files"

# Only the models the app uses, with caps, so the endpoint can't be used as a general-purpose free LLM.
ALLOWED_MODELS = {"llama-3.3-70b-versatile", "openai/gpt-oss-20b"}
MAX_TOKENS = 2048
MAX_MESSAGES = 50
MAX_TOTAL_CHARS = 100_000
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


class AIChatView(APIView):
    """POST {model, messages, temperature?, max_tokens?} -> Groq's chat-completions response, unchanged."""

    permission_classes = [IsAuthenticated]
    authentication_classes = [TokenAuthentication]

    def post(self, request):
        api_key = settings.GROQ_API_KEY
        if not api_key:
            return Response({"error": {"message": "AI is not configured on the server (GROQ_API_KEY)."}}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        model = request.data.get("model")
        messages = request.data.get("messages")
        if model not in ALLOWED_MODELS:
            return Response({"error": {"message": "Unsupported model."}}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(messages, list) or not messages or len(messages) > MAX_MESSAGES:
            return Response({"error": {"message": "messages must be a non-empty list."}}, status=status.HTTP_400_BAD_REQUEST)
        clean = []
        for m in messages:
            if not isinstance(m, dict) or m.get("role") not in ("system", "user", "assistant") or not isinstance(m.get("content"), str):
                return Response({"error": {"message": "Each message needs a role and text content."}}, status=status.HTTP_400_BAD_REQUEST)
            clean.append({"role": m["role"], "content": m["content"]})
        if sum(len(m["content"]) for m in clean) > MAX_TOTAL_CHARS:
            return Response({"error": {"message": "The conversation is too long."}}, status=status.HTTP_400_BAD_REQUEST)

        try:
            temperature = min(max(float(request.data.get("temperature", 0.7)), 0.0), 2.0)
            max_tokens = min(max(int(request.data.get("max_tokens", 1024)), 1), MAX_TOKENS)
        except (TypeError, ValueError):
            return Response({"error": {"message": "temperature and max_tokens must be numbers."}}, status=status.HTTP_400_BAD_REQUEST)

        try:
            upstream = requests.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": clean, "temperature": temperature, "max_tokens": max_tokens},
                timeout=90,
            )
        except requests.RequestException:
            return Response({"error": {"message": "The AI service could not be reached."}}, status=status.HTTP_502_BAD_GATEWAY)
        try:
            body = upstream.json()
        except ValueError:
            body = {"error": {"message": "The AI service returned an unreadable answer."}}
        return Response(body, status=upstream.status_code if upstream.ok else status.HTTP_502_BAD_GATEWAY)


class ResumeUploadView(APIView):
    """POST multipart {file: PDF up to 5 MB} -> Pinata's upload response ({"data": {"cid": ...}})."""

    permission_classes = [IsAuthenticated]
    authentication_classes = [TokenAuthentication]

    def post(self, request):
        jwt = os.getenv("PINATA_JWT")
        if not jwt:
            return Response({"error": "File uploads are not configured on the server (PINATA_JWT)."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        upload = request.FILES.get("file")
        if not upload:
            return Response({"error": "No file was sent."}, status=status.HTTP_400_BAD_REQUEST)
        if upload.size > MAX_UPLOAD_BYTES:
            return Response({"error": "File size should not exceed 5MB."}, status=status.HTTP_400_BAD_REQUEST)
        head = upload.read(5)
        upload.seek(0)
        if upload.content_type != "application/pdf" or head != b"%PDF-":
            return Response({"error": "Please upload a PDF file only."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            upstream = requests.post(
                PINATA_URL,
                headers={"Authorization": f"Bearer {jwt}"},
                files={"file": (upload.name, upload.read(), "application/pdf")},
                data={"network": "public"},
                timeout=120,
            )
        except requests.RequestException:
            return Response({"error": "The file service could not be reached."}, status=status.HTTP_502_BAD_GATEWAY)
        try:
            body = upstream.json()
        except ValueError:
            body = {"error": "The file service returned an unreadable answer."}
        return Response(body, status=upstream.status_code if upstream.ok else status.HTTP_502_BAD_GATEWAY)
