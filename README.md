# 🌐 Monitor de Rede & Latência

Um painel que fica de olho na sua internet **24 horas por dia** e mostra, de um jeito fácil de entender:

* 📶 se a internet está rápida ou lenta (latência e perda de pacotes);
* 🌐 se sites e apps como YouTube, Netflix, WhatsApp e jogos estão no ar;
* 🚨 **quando a internet caiu, por quanto tempo e de quem foi a culpa** (sua rede, a operadora ou só um site);
* 📈 em quais dias e horários a internet costuma piorar;
* 🖥️ o uso de CPU e memória do roteador (opcional).

Você abre o painel no navegador do computador **ou do celular**.

> ℹ️ Funciona no **Windows 10 e 11**. A leitura de CPU/memória do roteador foi testada no modem Wi-Fi 6 da **Vivo** (MitraStar GPT-2742GX4X5). Com outros roteadores, todo o resto funciona normalmente.

---

## 📋 Índice

1. [Antes de começar](#antes)
2. [Instalação passo a passo](#instalacao)
3. [Como usar no dia a dia](#dia-a-dia)
4. [Abrir no celular](#celular)
5. [Entendendo o painel](#painel)
6. [Problemas comuns](#problemas)
7. [Como desinstalar](#desinstalar)
8. [Para quem quer mexer no código](#codigo)

---

<a id="antes"></a>

## ✅ Antes de começar

Você vai precisar de:

| O quê | Por quê | Custa algo? |
| --- | --- | --- |
| Um computador com **Windows 10 ou 11** | É onde o monitor roda. | — |
| O **Python** instalado | É a linguagem em que o monitor foi feito. A instalação está explicada abaixo. | Grátis |
| **Internet** durante a instalação | Para baixar o Python e as bibliotecas. | — |
| *(Opcional)* usuário e senha SSH do roteador | Só para ver CPU e memória do roteador. Sem isso, todo o resto funciona. | — |

⏱️ Tempo total: uns **10 minutos**.

---

<a id="instalacao"></a>

## 🛠️ Instalação passo a passo

### Passo 1 — Instalar o Python

> Se você já tem o Python, pule para o Passo 2.

1. Acesse **<https://www.python.org/downloads/>** e clique no botão amarelo de download para Windows.
2. Abra o arquivo baixado e siga o instalador.
3. ⚠️ **Muito importante:** se aparecer a caixinha **`Add python.exe to PATH`**, **marque-a** antes de clicar em **Install Now**. Se o instalador perguntar (numa janela preta) se deve adicionar o Python ao PATH, responda **y** (sim). Sem isso, o monitor não encontra o Python.
4. Espere terminar e feche o instalador.

> ✔️ **Como conferir:** aperte a tecla Windows, digite `cmd`, abra o **Prompt de Comando**, digite `python --version` e aperte ENTER. Se aparecer algo como `Python 3.14.0`, deu certo.

### Passo 2 — Baixar o monitor

1. Nesta página do GitHub, clique no botão verde **`<> Code`** (no topo da lista de arquivos).
2. Clique em **Download ZIP**.
3. Abra a pasta **Downloads**, clique com o botão direito no arquivo `monitor-rede-main.zip` e escolha **Extrair tudo…** → **Extrair**.
4. Mova a pasta extraída para um lugar fixo, por exemplo `C:\MonitorRede`.
   > 💡 Escolha um lugar definitivo: se você mover a pasta depois, vai precisar rodar o `Instalar.bat` de novo.

<details>
<summary>Sabe usar Git? Clique aqui.</summary>

```bash
git clone https://github.com/ogandolfo/monitor-rede.git
```
</details>

### Passo 3 — Rodar o instalador

1. Abra a pasta do monitor e dê **dois cliques em `Instalar.bat`**.
   > 🛡️ Se aparecer uma tela azul **"O Windows protegeu o computador"**, clique em **Mais informações** → **Executar assim mesmo**. Isso acontece com qualquer arquivo baixado da internet. Dá para abrir o `.bat` no Bloco de Notas e ver exatamente o que ele faz.
2. Uma janela preta vai abrir e instalar as bibliotecas sozinha (pode levar alguns minutos).
3. Depois ela faz **2 perguntas**. Em todas, o valor entre `[colchetes]` é usado se você só apertar **ENTER**:

   | Pergunta | O que responder |
   | --- | --- |
   | **IP do roteador** | Aperte **ENTER**: o instalador já detecta sozinho. |
   | **Configurar o acesso SSH ao roteador?** | Se tem o modem Vivo e sabe o usuário/senha, responda **s** e digite-os (a senha não aparece enquanto você digita, é normal). Se não, responda **n**. |
   | **Iniciar o monitor sozinho quando o Windows ligar?** | Recomendo **s**: assim ele grava o histórico o tempo todo. |

4. Quando aparecer **PRONTO!**, pode fechar a janela.

> 🔐 A senha do roteador é guardada no **Gerenciador de Credenciais do Windows** (o mesmo cofre que o Windows usa para senhas de rede), e não num arquivo de texto.

### Passo 4 — Abrir o painel

* Abra o navegador e acesse **<http://localhost:8501>**
  *(ou dê dois cliques em `Executar_Monitor.bat`, que abre sozinho).*
* Na primeira vez, aguarde uns 10 segundos para chegarem as primeiras medições.
* Se o Windows perguntar sobre o **Firewall**, marque **Redes privadas** e clique em **Permitir**. Isso é necessário para abrir no celular.

🎉 **Pronto!** O monitor está funcionando.

---

<a id="dia-a-dia"></a>

## 📅 Como usar no dia a dia

| Quero… | Faça isto |
| --- | --- |
| Ver o painel | Acesse <http://localhost:8501> no navegador. |
| Abrir o monitor (se ele não inicia com o Windows) | Dois cliques em `Executar_Monitor.bat`. Se ele já estiver rodando, só abre o painel. |
| Fazer ele iniciar sozinho com o Windows | Dois cliques em `Iniciar_com_Windows.bat`. |
| Parar de iniciar com o Windows | Dois cliques em `Remover_Inicializacao.bat`. |
| Reiniciar o monitor (ex.: depois de mudar uma configuração) | Dois cliques em `Iniciar_com_Windows.bat`. |
| Trocar a senha do roteador | No painel: aba **ONT (SSH)** → **Credenciais SSH**. |
| Mudar o IP do roteador ou refazer a configuração | Rode o `Instalar.bat` de novo. |

> 💡 O monitor só mede enquanto o computador está ligado. Os períodos com o PC desligado aparecem no histórico como **💤 Monitor desligado**, para você não confundir com queda de internet.

---

<a id="celular"></a>

## 📱 Abrir no celular

1. O celular precisa estar no **mesmo Wi-Fi** do computador.
2. Descubra o IP do computador: abra o **Prompt de Comando**, digite `ipconfig` e procure **Endereço IPv4** (algo como `192.168.15.18`).
3. No navegador do celular, acesse `http://SEU-IP:8501` (por exemplo, `http://192.168.15.18:8501`).
4. 💡 Salve nos favoritos ou adicione à tela inicial.

O painel se ajusta à tela do celular sozinho.

<details>
<summary>🔒 Quero que peça senha no celular (opcional)</summary>

Por padrão o painel abre sem senha, o que é ok numa rede de casa em que você confia. Se tem visitas ou um Wi-Fi compartilhado:

* Dê dois cliques em **`Definir_Senha_Painel.bat`** e escolha uma senha. Ela será pedida em outros aparelhos; neste computador o painel continua abrindo direto.
* Para tirar a senha, abra o Prompt de Comando na pasta do monitor e rode `python -m netmon.credentials painel --remover`.

Para o painel só abrir **neste computador**, abra o arquivo `.streamlit\config.toml` no Bloco de Notas e troque `address = "0.0.0.0"` por `address = "localhost"`.
</details>

---

<a id="painel"></a>

## 🔎 Entendendo o painel

O painel tem 4 abas:

| Aba | O que mostra |
| --- | --- |
| **⚡ Latência & DNS** | A cada 5 segundos, mede o tempo de resposta (ping) de 9 servidores da internet e do seu roteador. Verde = ok, laranja = perdeu algum pacote, vermelho = sem resposta. |
| **🌐 Serviços Web** | A cada 60 segundos, verifica se 20 sites e apps estão respondendo e quão rápido. |
| **📈 Histórico** | Os últimos 180 dias: tempo total sem internet, quantas quedas, gráficos, o mapa de "em que horário piora" e a lista de quedas. |
| **📡 ONT (SSH)** | CPU, memória e há quanto tempo o roteador está ligado (se você configurou o SSH). |

### 📖 Palavras que aparecem no painel

* **Latência (ms)** — quanto tempo um "recado" leva para ir até um servidor e voltar, em milissegundos. **Quanto menor, melhor.** Em fibra, o normal é entre 5 e 20 ms.
* **Perda de pacotes (%)** — quantos desses recados se perderam no caminho. O ideal é **0%**. Perda causa travadas em jogos, chamadas de vídeo e VPN.
* **Gateway** — o seu roteador. Se ele não responde, o problema está **dentro da sua casa**.
* **DNS públicos** — servidores conhecidos da internet (Google, Cloudflare…), usados como "termômetro" da sua conexão.

### 🚨 Registro de quedas

Toda vez que algo dá errado, o monitor anota o início, o fim, a duração e a **causa provável**:

| Causa | O que significa | O que fazer |
| --- | --- | --- |
| 🏠 **Rede local** | O roteador parou de responder. | Verifique o Wi-Fi, os cabos e reinicie o roteador. |
| 🌐 **Internet / Operadora** | O roteador está ok, mas a internet não. | O problema é da operadora: guarde o registro e ligue para ela. |
| 〰️ **Instabilidade** | A internet está no ar, mas lenta ou perdendo pacotes (perda ≥ 10% ou latência ≥ 100 ms por 15 segundos). | Se acontece sempre no mesmo horário, veja o mapa de calor. |
| 🧩 **Serviço fora do ar** | Sua internet está ok, mas um site específico não responde. | O problema é daquele site, não seu. |
| 💤 **Monitor desligado** | O computador estava desligado. | Nada: só não há medições desse período. |

* Falhas de poucos segundos são ignoradas: uma queda só é registrada depois de **10 segundos seguidos**.
* Problemas acontecendo agora aparecem num **aviso vermelho no topo** do painel.
* O botão **⬇️ Baixar registro (CSV)** gera uma planilha (abre no Excel) que serve de **prova** ao reclamar com a operadora ou na Anatel.

### 🗓️ Cores do mapa de calor

O mapa mostra a média de cada **dia da semana × hora**. As cores seguem uma régua fixa, pensada para quem joga online, trabalha com VPN ou faz chamadas de vídeo:

| | 🟢 ótimo | 🟡 aceitável | 🟠 ruim | 🔴 péssimo |
| --- | --- | --- | --- | --- |
| **Latência** | até 20 ms | ~40 ms | ~70 ms | 100 ms ou mais |
| **Perda de pacotes** | 0% | ~2% | ~5% | 10% ou mais |

### 🔍 Dicas dos gráficos

* **Zoom:** roda do mouse em cima do gráfico. **Duplo clique** volta ao normal.
* O painel se atualiza a cada 5 segundos, o que desfaz o zoom. Para analisar com calma, ligue **⏸️ Pausar tela** no topo. A coleta continua normalmente por trás.

---

<a id="problemas"></a>

## 🆘 Problemas comuns

<details>
<summary><b>"python não é reconhecido como um comando interno"</b></summary>

O Python foi instalado sem marcar **Add python.exe to PATH**. Rode o instalador do Python de novo, escolha **Modify** → **Next** e marque **Add Python to environment variables**. Ou desinstale e reinstale marcando a caixinha. Depois rode o `Instalar.bat` de novo.
</details>

<details>
<summary><b>A página http://localhost:8501 não abre</b></summary>

O monitor não está rodando. Dê dois cliques em `Executar_Monitor.bat` e aguarde uns 10 segundos. Se a janela preta mostrar um erro, rode o `Instalar.bat` de novo.
</details>

<details>
<summary><b>Não abre no celular</b></summary>

* Confira se o celular está no mesmo Wi-Fi (e não no 4G/5G).
* Confira o IP do computador com `ipconfig` (ele pode mudar quando o roteador reinicia).
* Libere o Python no Firewall: menu Iniciar → **Firewall do Windows Defender** → **Permitir um aplicativo** → marque **Python** em **Privada**.
</details>

<details>
<summary><b>Aba ONT (SSH): "Usuário ou senha incorretos" ou "Credenciais não configuradas"</b></summary>

Na aba **ONT (SSH)**, abra **⚙️ Credenciais SSH**, digite o usuário e a senha corretos e clique em **Salvar e reconectar**. Se você não tem o modem Vivo MitraStar, pode ignorar essa aba.
</details>

<details>
<summary><b>Aba ONT (SSH): "A chave SSH da ONT mudou"</b></summary>

É uma proteção. Na primeira conexão, o monitor memoriza a "impressão digital" do roteador; se ela muda, ele se recusa a conectar.

* **Você resetou ou trocou o roteador?** Então é esperado: apague o arquivo `data\ont_known_hosts` dentro da pasta do monitor e reinicie o monitor.
* **Não mexeu em nada?** Desconfie: pode haver outro aparelho na rede se passando pelo roteador.
</details>

<details>
<summary><b>"O monitor já está rodando em outra janela"</b></summary>

Só pode rodar uma cópia por vez. Ele provavelmente já está rodando em segundo plano: é só abrir <http://localhost:8501>.
</details>

---

<a id="desinstalar"></a>

## 🗑️ Como desinstalar

1. Dê dois cliques em `Remover_Inicializacao.bat`.
2. Apague a pasta do monitor. **Atenção:** isso apaga também o histórico.
3. *(Opcional)* Apague as senhas guardadas: menu Iniciar → **Gerenciador de Credenciais** → **Credenciais do Windows** → remova os itens **NetMon-ONT** e **NetMon-Painel**.

---

<a id="codigo"></a>

## 🧑‍💻 Para quem quer mexer no código

<details>
<summary>Detalhes técnicos</summary>

### Como funciona

* Feito em Python com [Streamlit](https://streamlit.io/) (painel) e [Altair](https://altair-viz.github.io/) (gráficos).
* `run.py` liga um **coletor em segundo plano** (threads de ping, HTTP e SSH) antes de subir o painel, então o histórico é gravado mesmo sem ninguém olhando a página. Uma trava impede duas cópias rodando ao mesmo tempo.
* O histórico fica em **SQLite** (`data/netmon.db`): médias por minuto dos pings, cada checagem HTTP, cada coleta da ONT e os incidentes. Os dados com mais de 180 dias são apagados automaticamente.
* A inicialização com o Windows é uma tarefa do **Agendador de Tarefas** do usuário (`pythonw`, sem janela), criada por `scripts/autostart.ps1`.

### Instalação manual (sem o Instalar.bat)

```bash
python -m pip install -r requirements.txt
python -m netmon.credentials ont      # guarda a senha SSH no Gerenciador de Credenciais
python run.py                         # painel em http://localhost:8501
```

O arquivo `.env` (na raiz) aceita `ONT_IP` (IP do roteador, também usado como gateway) e `ONT_USER`. Um `ONT_PASS` no `.env` é migrado automaticamente para o Gerenciador de Credenciais na primeira execução.

### Segurança

* Senha da ONT no Gerenciador de Credenciais do Windows (`keyring`), nunca enviada ao navegador.
* Chave SSH da ONT fixada no primeiro uso (`data/ont_known_hosts`); se mudar, a conexão é recusada.
* Senha opcional do painel, guardada só como hash PBKDF2, exigida apenas em acessos vindos de outros aparelhos.
* Os sites são checados a cada 60 s, e não a cada 5 s, para não sobrecarregar os servidores nem ser bloqueado por eles.

### Personalização

Intervalos, limites do diagnóstico, régua de cores (`HEAT_LATENCY_STOPS_MS`, `HEAT_LOSS_STOPS_PCT`), retenção e as listas de alvos (`DNS_TARGETS`, `SERVICES`) ficam em [`netmon/config.py`](netmon/config.py). Depois de alterar, reinicie com `Iniciar_com_Windows.bat`.

### Estrutura

| Caminho | Papel |
| --- | --- |
| `Instalar.bat` / `netmon/instalar.py` | Instalador e assistente de configuração. |
| `run.py` | Ponto de entrada: liga a coleta e sobe o painel. |
| `monitor.py` | Painel Streamlit (abas, gráficos, histórico). |
| `netmon/config.py` | Configurações, limites e listas de alvos. |
| `netmon/probes.py` | Sondas: ping, HTTP e SSH da ONT. |
| `netmon/collector.py` | Coletor em segundo plano. |
| `netmon/incidents.py` | Detecção de quedas e diagnóstico da causa. |
| `netmon/storage.py` | Histórico em SQLite. |
| `netmon/credentials.py` | Senhas no Gerenciador de Credenciais do Windows. |
| `scripts/autostart.ps1` | Registra/remove a tarefa de inicialização. |
| `.streamlit/config.toml` | Endereço de rede, porta e tema do painel. |
| `data/` *(fora do Git)* | `netmon.db` (histórico), `ont_known_hosts` (chave SSH fixada), `netmon.log` (log em segundo plano). |

</details>
