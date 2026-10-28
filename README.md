# ytmine

Baixa vídeos do YouTube — **somente** os que são seus (seu próprio canal) ou os que
estão sob **licença Creative Commons**. Nada mais passa.

O yt-dlp baixa qualquer coisa. O ytmine é o oposto: ele pergunta à API oficial do
YouTube qual é a licença do vídeo, e se a resposta não for "Creative Commons" ou
"seu upload", ele nem chega a buscar os bytes.

## Por que ele existe

`yt-dlp` existe e faz o que faz. O problema é que ele não tem opinião: com ele,
baixar um vídeo de licença padrão de um terceiro é indistinguível de baixar o seu
próprio backup. O ytmine coloca a decisão de direitos na frente da transferência,
de vez, em um lugar que dá para testar.

## O que ele baixa

| Situação | Resultado |
|---|---|
| Vídeo com licença `creativeCommon` | baixa |
| Vídeo do canal autenticado (seu upload, inclusive privado) | baixa |
| Qualquer outro vídeo de licença `youtube` | **bloqueado**, sem tocar na rede de mídia |

Não existe allowlist, nem flag `--force-license`, nem bypass. A política mora em
[`src/ytmine/gate.py`](src/ytmine/gate.py) e é código puro, testado offline.

## Instalação

```bash
uv sync
```

Dependências externas: [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) e `ffmpeg`
no `PATH` (o yt-dlp só usa o ffmpeg para juntar vídeo e áudio).

## Configuração (uma vez)

O ytmine não usa API key: só OAuth, porque é assim que ele descobre qual canal é
seu.

1. No [Google Cloud Console](https://console.cloud.google.com/): crie um projeto,
   habilite **YouTube Data API v3** e crie um cliente OAuth do tipo
   **Desktop app**.
2. Salve o JSON baixado em `~/.config/ytmine/client_secrets.json`.
3. Rode:

```bash
ytmine auth
```

Ele abre o navegador, você autoriza, cola a URL de redirecionamento de volta, e o
token fica salvo em `~/.config/ytmine/token.json` com permissão `0600`.

Confira os caminhos com `ytmine paths`.

## Uso

```bash
# só consulta: qual é a licença, e ele baixaria?
ytmine check "https://www.youtube.com/watch?v=XXXXXXXXXXX"

# baixa um ou vários
ytmine download "https://youtu.be/XXXXXXXXXXX" "https://www.youtube.com/shorts/XXXXXXXXXXX"

# baixa seus próprios vídeos, do mais recente ao mais antigo
ytmine channel --limit 50

# ensaia sem baixar nada
ytmine channel --dry-run
```

Opções globais:

| Flag | Efeito |
|---|---|
| `--out DIR` | destino (padrão `~/Downloads/ytmine`) |
| `--quality FMT` | formato do yt-dlp (padrão `bv*+ba/b`) |
| `--parallel N` | downloads simultâneos, 1 a 8 (padrão 1) |
| `--dry-run` | mostra a decisão sem baixar |
| `--force` | ignora o arquivo de histórico |

`ytmine` aceita link de watch, `youtu.be`, `shorts`, `live`, `embed`, e o ID
puro. Qualquer host que não seja do YouTube é recusado no parse — não existe
modo "qualquer site".

## Como funciona

```
URL ──► parse (só YouTube) ──► videos.list ──► gate ──► yt-dlp
                                     │
                              channels.list (mine)
```

1. **`videos.py`** — parse do link. Host fora do YouTube é erro, não aviso.
2. **`api.py`** — `videos.list?part=snippet,status` e `channels.list?mine=true`
   via [httpx2](https://github.com/pydantic/httpx2). A resposta vira modelo
   Pydantic direto do texto; nada de JSON solto no código.
3. **`gate.py`** — a política. `creativeCommon` passa. Seu canal passa. O resto
   vira `Refused`.
4. **`backend.py`** — só depois do gate, o `yt-dlp` roda como subprocesso.

O passo 4 é a parte honesta da explicação: o YouTube **não** expõe endpoint de
download de mídia. Os bytes sempre vêm do yt-dlp. O que o ytmine garante é que
ele só recebe vídeos cuja licença a API oficial já confirmou.

## Testes

```bash
uv run pytest
uv run ruff check .
uv run basedpyright
```

O gate, o parse de URL, a construção do comando do backend e o mapeamento dos
modelos são todos testáveis sem rede e sem credencial.

## Licença

MIT. Veja [LICENSE](LICENSE).
