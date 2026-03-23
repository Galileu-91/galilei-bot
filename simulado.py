import discord
from discord.ext import commands
from discord.ui import Button, View

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Simulação de base de dados (Aqui você cola o texto das suas questões)
questoes_exemplo = [
    {
        "pergunta": "No Planejamento Estratégico de TI, qual o foco principal?",
        "opcoes": ["A) Reduzir custos apenas", "B) Alinhamento com o negócio", "C) Comprar hardware novo", "D) Trocar senhas"],
        "correta": "B"
    }
]
class MenuSimulado(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Planejamento Estratégico de TI", style=discord.ButtonStyle.green)
    async def iniciar_pete(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Começa da questão 0 (primeira da lista) com 0 acertos
        q = questoes_exemplo[0]
        msg = f"🚀 **Iniciando Simulado!**\n\n**Questão 1:**\n{q['pergunta']}"
        await interaction.response.send_message(msg, view=QuestaoView(0, 0))

class QuestaoView(View):
    def __init__(self, index, acertos):
        super().__init__(timeout=None)
        self.index = index
        self.acertos = acertos
        # Cria os botões A, B, C, D automaticamente
        for letra in ["A", "B", "C", "D"]:
            self.add_item(self.criar_botao(letra))

    def criar_botao(self, letra):
        btn = Button(label=letra, style=discord.ButtonStyle.blurple, custom_id=letra)
        btn.callback = self.check_answer
        return btn

    async def check_answer(self, interaction: discord.Interaction):
        escolha = interaction.data['custom_id']
        correta = questoes_exemplo[self.index]["correta"]
        
        # 1. Calcula se acertou
        novos_acertos = self.acertos
        if escolha.upper() == correta.upper():
            novos_acertos += 1
            feedback = "✅ **Acertou!**"
        else:
            feedback = f"❌ **Errou!** A correta era **{correta}**."
        
        # 2. Verifica se tem próxima questão
        proximo_index = self.index + 1
        
        if proximo_index < len(questoes_exemplo):
            q_proxima = questoes_exemplo[proximo_index]
            texto_final = f"{feedback}\n\n---\n**Questão {proximo_index + 1}:**\n{q_proxima['pergunta']}"
            # Edita a mensagem para a próxima questão
            await interaction.response.edit_message(content=texto_final, view=QuestaoView(proximo_index, novos_acertos))
        else:
            # 3. Fim do simulado
            await interaction.response.edit_message(
                content=f"{feedback}\n\n🏆 **Fim do Simulado!**\nSua nota final: **{novos_acertos}/{len(questoes_exemplo)}**", 
                view=None
            )   
@bot.command()
async def menu(ctx):
    await ctx.send("Escolha uma disciplina para estudar:", view=MenuSimulado())

import os
from dotenv import load_dotenv
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
bot.run(TOKEN)