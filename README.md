# 🌐 Monitor de Rede & Latência

Monitor doméstico em Python + **Streamlit** que acompanha a sua internet 24h: latência, perda de pacotes, disponibilidade de sites e o hardware do roteador. Ele **guarda o histórico**, **registra cada queda com a causa provável** e pode **iniciar sozinho com o Windows**.

> ℹ️ **Compatibilidade:** a telemetria de hardware (aba ONT) foi desenvolvida e testada para o **Modem Wi-Fi 6 da Vivo** (MitraStar **GPT-2742GX4X5**). O ping usa a sintaxe do Windows (`ping -n`).

---

## 🚀 Funcionalidades

| Aba | O que mostra |
| --- | --- |
| **⚡ Latência & DNS** | Ping a cada 5s em 9 DNS públicos e no gateway: latência, perda e gráficos dos últimos 30 min. |
| **🌐 Serviços Web** | Checagem HTTP a cada 60s de redes sociais, streaming e jogos: tempo de resposta e disponibilidade. |
| **📈 Histórico** | Até 180 dias guardados em disco: tempo sem internet, nº de quedas, gráficos por período, mapa de calor *dia da semana × hora* ("em que horário a internet piora?") e o **registro de quedas**, exportável em CSV. |
| **📡 ONT (SSH)** | Uptime, RAM e CPU do roteador a cada 120s. |

### 🚨 Registro de quedas com diagnóstico

Cada problema vira um registro com início, fim, duração e **causa provável**:

| Causa | Quando |
| --- | --- |
| 🏠 **Rede local** | O roteador (gateway) parou de responder → Wi-Fi, cabo ou roteador. |
| 🌐 **Internet / Operadora** | O roteador responde, mas quase todos os DNS públicos não → problema da operadora. |
| 〰️ **Instabilidade** | Internet no ar, mas com perda ≥ 30% ou latência ≥ 150 ms. |
| 🧩 **Serviço fora do ar** | Internet ok, mas um site específico falhou por 2 checagens seguidas. |
| 💤 **Monitor desligado** | Período sem dados (PC desligado ou monitor fechado). |

Falhas isoladas de poucos segundos são ignoradas (um incidente só abre após 10s seguidos). Problemas em andamento aparecem num alerta vermelho no topo do painel. O CSV serve como prova ao reclamar com a operadora ou na Anatel.

---

## 🛠️ Instalação

Requisitos: **Windows** com **Python 3.10+**.

```bash
python -m pip install -r requirements.txt
```

Crie um arquivo `.env` na pasta do projeto:

```env
ONT_IP=192.168.15.1
ONT_USER=seu_usuario
ONT_PASS=sua_senha
```

Na primeira execução a senha `ONT_PASS` é **copiada para o Gerenciador de Credenciais do Windows**. Depois disso você pode (e deve) apagar a linha `ONT_PASS` do `.env`. Para trocar a senha depois, use a aba **ONT (SSH) → Credenciais SSH** ou rode `python -m netmon.credentials ont`.

---

## 🏃 Como executar

| Arquivo | Para quê |
| --- | --- |
| `Executar_Monitor.bat` | Abre o monitor com janela. Se ele já estiver rodando, só abre o painel. |
| `Iniciar_com_Windows.bat` | Registra o monitor para iniciar **sozinho e sem janela** sempre que você entrar no Windows, e já o inicia. |
| `Remover_Inicializacao.bat` | Desfaz o item acima. |
| `Definir_Senha_Painel.bat` | Define a senha pedida quando o painel é aberto de **outro aparelho** (ex.: celular). |

Pelo terminal: `python run.py`. O painel abre em <http://localhost:8501>.

O `run.py` liga a coleta **antes** do painel, então o histórico é gravado mesmo que ninguém abra a página. Só uma cópia do monitor roda por vez (uma segunda tentativa é recusada).

---

## 📱 Acesso pelo celular

No celular (mesmo Wi-Fi), abra `http://<IP-deste-PC>:8501`. O endereço aparece no terminal como *Network URL*. O layout se adapta à tela.

* Se não abrir, libere o Python no Firewall do Windows.
* **Recomendado:** rode `Definir_Senha_Painel.bat` para exigir senha nos acessos pela rede. Neste PC o painel continua abrindo sem senha.
* Para restringir só a este PC, troque `address` para `"localhost"` em [.streamlit/config.toml](.streamlit/config.toml).

### 🔍 Gráficos

* O eixo vertical sempre começa em 0; perda e disponibilidade vão de 0 a 100%.
* Zoom com a roda do mouse e arraste no eixo do tempo; **duplo clique** volta ao normal.
* Ative **⏸️ Pausar tela** para dar zoom sem que a atualização a cada 5s o desfaça (a coleta continua).

---

## 🔒 Segurança

* **Senha da ONT** no Gerenciador de Credenciais do Windows, nunca enviada ao navegador.
* **Senha do painel** opcional, guardada só como hash (PBKDF2) no Gerenciador de Credenciais.
* **Chave SSH da ONT fixada:** na primeira conexão a chave do roteador é gravada em `data/ont_known_hosts`. Se ela mudar, a conexão é recusada com um aviso. Se você resetou ou trocou o roteador, apague esse arquivo.
* Os sites são checados a cada 60s (e não a cada 5s) para não sobrecarregar os servidores nem ser bloqueado por eles.

---

## 📂 Arquivos gerados (pasta `data/`, fora do Git)

| Arquivo | Conteúdo |
| --- | --- |
| `netmon.db` | Histórico (SQLite): médias por minuto, checagens HTTP, coletas da ONT e incidentes. |
| `ont_known_hosts` | Chave SSH fixada da ONT. |
| `netmon.log` | Mensagens do monitor quando roda em segundo plano. |

---

## 🔧 Personalização

Intervalos, limites de diagnóstico, tempo de retenção e as listas de alvos (`DNS_TARGETS`, `SERVICES`) ficam em [netmon/config.py](netmon/config.py).
