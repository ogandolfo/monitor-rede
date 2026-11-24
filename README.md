# 🌐 Monitor de Rede & Latência

Aplicação em Python com **Streamlit** para monitorar em tempo real a latência da conexão, a disponibilidade de serviços web e a telemetria de hardware do roteador via SSH.

> ℹ️ **Compatibilidade:** a telemetria de hardware (Aba 3) foi desenvolvida e testada para o **Modem Wi-Fi 6 da Vivo** (MitraStar **GPT-2742GX4X5**). O ping usa a sintaxe do Windows (`ping -n`).

---

## 🚀 Funcionalidades

* **⚡ Latência & DNS Públicos:** ping a cada 5s em 9 servidores DNS públicos e no gateway, com latência (ms), perda de pacotes (%) e histórico de 30 minutos.
* **🌐 Serviços Web:** checagem HTTP/HTTPS a cada 5s de redes sociais, streaming, jogos e outros serviços, com tempo de resposta e disponibilidade (%) nos últimos 30 minutos.
* **📡 Métricas da ONT (SSH):** uptime, uso de RAM e de CPU coletados a cada 120s, com histórico das últimas 30 coletas.

A coleta roda **em segundo plano**, independente do navegador: o histórico continua sendo gravado mesmo com a aba fechada e é compartilhado entre todas as abas abertas. O histórico fica só em memória e é zerado quando o programa é fechado.

---

## 🛠️ Pré-requisitos

* **Windows** com **Python 3.10+**
* Conexão com a rede local da ONT e acesso SSH habilitado.

Instale as dependências:

```bash
python -m pip install -r requirements.txt
```

---

## ⚙️ Configuração (`.env`)

Crie um arquivo `.env` na raiz do projeto com os dados da ONT:

```env
ONT_IP=192.168.15.1
ONT_USER=seu_usuario
ONT_PASS=sua_senha
```

* `ONT_IP` também é usado como **Gateway** na aba de latência (padrão: `192.168.1.1`).
* O `.env` já está no `.gitignore`, então não é enviado ao GitHub.
* As credenciais também podem ser trocadas na própria interface (Aba 3 → *Credenciais SSH*), sem reiniciar. A senha nunca é exibida no navegador.

### 📱 Acesso pelo celular

O painel fica disponível para **toda a rede local**. No celular (no mesmo Wi-Fi), abra `http://<IP-deste-PC>:8501` — o endereço aparece no terminal como *Network URL*. O layout se adapta à tela (cartões em 2 colunas, gráficos empilhados).

* Se não abrir, libere o Python no Firewall do Windows (o próprio Windows pergunta na primeira execução).
* Qualquer pessoa na sua rede pode ver o painel (a senha SSH nunca é exibida). Para restringir só a este PC, troque `address` para `"localhost"` em [.streamlit/config.toml](.streamlit/config.toml).

### 🔍 Gráficos

* O eixo vertical sempre começa em 0; perda e disponibilidade vão de 0 a 100%.
* Zoom com a roda do mouse e arraste no eixo do tempo; **duplo clique** volta ao normal.
* Ative **⏸️ Pausar tela** para analisar com zoom sem que a atualização a cada 5s desfaça o zoom (a coleta continua em segundo plano).
* A legenda abaixo de cada gráfico mostra todos os nomes e quebra linha conforme a largura da tela.

---

## 🏃 Como executar

**Opção 1:** dê um duplo clique em `Executar_Monitor.bat`.

**Opção 2:** pelo terminal, na pasta do projeto:

```bash
python -m streamlit run monitor.py
```

O painel abre em <http://localhost:8501>.

---

## 🔧 Personalização

No topo de `monitor.py` ficam os intervalos de coleta (`PROBE_INTERVAL_S`, `SSH_INTERVAL_S`), o tamanho do histórico e as listas `DNS_TARGETS` e `SERVICES`. Para adicionar ou remover um alvo, basta editar essas listas.
