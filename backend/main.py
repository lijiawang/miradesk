from app.main import app


if __name__ == "__main__":
    import os
    import socket
    import uvicorn

    def find_available_port(host: str, preferred_port: int, max_tries: int = 20) -> int:
        """优先使用 preferred_port；若被占用则向上递增寻找可用端口。"""
        for port in range(preferred_port, preferred_port + max_tries):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    s.bind((host, port))
                    return port
                except OSError:
                    continue
        return preferred_port

    host = os.getenv("HOST", "0.0.0.0")
    preferred_port = int(os.getenv("PORT", "8000"))

    port = preferred_port
    if os.getenv("PORT") is None:
        port = find_available_port(host, preferred_port)

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=os.getenv("RELOAD", "0") == "1",
        log_level="info",
    )
