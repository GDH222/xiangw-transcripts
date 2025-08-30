import discord
from discord.ext import commands
from discord import ui, ButtonStyle, SelectOption
import asyncio
import os
import re
import time
import math
import shutil
from typing import Optional, Dict, List
from pathlib import Path
from datetime import datetime

# Global variables
user_cooldowns = {}
COOLDOWN_SECONDS = 30

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="$", intents=intents)

class TicketForm(ui.Modal, title="Trade Information"):
    your_side = ui.TextInput(
        label="What is your side of the trade?",
        placeholder="What you're offering...",
        style=discord.TextStyle.long
    )
    their_side = ui.TextInput(
        label="What is their side of the trade?",
        placeholder="What they're offering...",
        style=discord.TextStyle.long
    )
    their_id = ui.TextInput(
        label="What is their user ID?",
        placeholder="Their Discord user ID..."
    )
    tip = ui.TextInput(
        label="What is the tip? (optional for trades below $50)",
        placeholder="Tip amount (optional)...",
        required=False
    )

    def __init__(self, ticket_type: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ticket_type = ticket_type
        if "trial" in ticket_type.lower() or "beginner" in ticket_type.lower():
            self.tip.required = False
            self.tip.label = "Tip (optional)"
        else:
            self.tip.required = True
            self.tip.label = "Tip (required for trades $50+)"

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        cog = interaction.client.get_cog("TicketBot")
        await cog.process_ticket_form(interaction, self.ticket_type, self.your_side.value, 
                                    self.their_side.value, self.their_id.value, self.tip.value)

class TicketPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketTypeSelect())

class TicketTypeSelect(ui.Select):
    def __init__(self):
        options = [
            SelectOption(label="Trial Middleman - $25/6.5K Rbx and below", value="trial_middleman"),
            SelectOption(label="Beginner Middleman - $50/13K Rbx and below", value="beginner_middleman"),
            SelectOption(label="Advanced Middleman - $100/25K Rbx and below", value="advanced_middleman"),
            SelectOption(label="Head Middleman - Above $100/25K Rbx", value="head_middleman")
        ]
        super().__init__(
            placeholder="Select middleman service needed...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_type_select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TicketForm(self.values[0]))

class TicketControlView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @ui.button(label="Close Ticket", style=ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        cog = interaction.client.get_cog("TicketBot")
        await cog.close_ticket(interaction)
    
    @ui.button(label="Transcript", style=ButtonStyle.blurple, custom_id="generate_transcript")
    async def generate_transcript(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        cog = interaction.client.get_cog("TicketBot")
        await cog.generate_transcript(interaction)
    
    @ui.button(label="Delete", style=ButtonStyle.grey, custom_id="delete_ticket")
    async def delete_ticket(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        cog = interaction.client.get_cog("TicketBot")
        await cog.delete_ticket(interaction)

class TicketOpenView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @ui.button(label="Open Ticket", style=ButtonStyle.green, custom_id="open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        cog = interaction.client.get_cog("TicketBot")
        await cog.open_ticket_button(interaction)
    
    @ui.button(label="Transcript", style=ButtonStyle.blurple, custom_id="generate_transcript_closed")
    async def generate_transcript_closed(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        cog = interaction.client.get_cog("TicketBot")
        await cog.generate_transcript(interaction)
    
    @ui.button(label="Delete", style=ButtonStyle.grey, custom_id="delete_ticket_closed")
    async def delete_ticket_closed(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        cog = interaction.client.get_cog("TicketBot")
        await cog.delete_ticket(interaction)

class TicketBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ticket_category_name = "TICKETS"
        self.transcripts_channel_name = "ticket-transcripts"
        self.support_roles = {
            "trial_middleman": "Trial Middleman",
            "beginner_middleman": "Beginner Middleman", 
            "advanced_middleman": "Advanced Middleman",
            "head_middleman": "Head Middleman"
        }
        self.ticket_counter = 1
        self.TICKET_CATEGORY_ID = None
        self.ticket_members: Dict[int, List[int]] = {}
        
        # Transcripts directory setup
        self.transcripts_dir = Path("static/transcripts")
        self.transcripts_dir.mkdir(exist_ok=True, parents=True)
        self.website_url = os.environ.get("WEBSITE_URL", "http://localhost:5000")

    async def cog_load(self):
        self.bot.add_view(TicketPanelView())
        self.bot.add_view(TicketControlView())
        self.bot.add_view(TicketOpenView())

    async def is_ticket_channel(self, channel: discord.TextChannel) -> bool:
        if not channel.category:
            return False
        if self.TICKET_CATEGORY_ID is None:
            category = discord.utils.get(channel.guild.categories, name=self.ticket_category_name)
            if category:
                self.TICKET_CATEGORY_ID = category.id
        return channel.category.id == self.TICKET_CATEGORY_ID

    async def has_permission(self, member: discord.Member) -> bool:
        if member.guild_permissions.administrator:
            return True
        for role_name in self.support_roles.values():
            support_role = discord.utils.get(member.guild.roles, name=role_name)
            if support_role and support_role in member.roles:
                return True
        return False

    async def create_html_transcript(self, channel: discord.TextChannel) -> str:
        """Create HTML transcript content"""
        messages = []
        async for message in channel.history(limit=None, oldest_first=True):
            messages.append({
                "timestamp": message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                "author": message.author.display_name,
                "content": message.clean_content,
                "attachments": [{"url": att.url, "filename": att.filename} 
                               for att in message.attachments]
            })
        
        # Generate HTML using Python string formatting
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Transcript #{channel.name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
        .header {{ text-align: center; margin-bottom: 30px; border-bottom: 2px solid #eee; padding-bottom: 20px; }}
        .message {{ margin: 15px 0; padding: 15px; border-left: 4px solid #007bff; background: #f8f9fa; border-radius: 4px; }}
        .timestamp {{ color: #6c757d; font-size: 0.9em; margin-bottom: 5px; }}
        .author {{ font-weight: bold; color: #495057; }}
        .content {{ margin: 5px 0; line-height: 1.5; }}
        .attachments {{ margin-top: 10px; }}
        .attachment {{ display: block; color: #007bff; text-decoration: none; margin: 5px 0; }}
        .attachment:hover {{ text-decoration: underline; }}
        .back-link {{ display: inline-block; margin-top: 20px; color: #6c757d; text-decoration: none; }}
        .back-link:hover {{ color: #495057; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Transcript #{channel.name}</h1>
            <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <a href="/" class="back-link">← Back to all transcripts</a>
        </div>
        <div class="messages">
"""
        
        for msg in messages:
            attachments_html = ""
            if msg['attachments']:
                attachments_html = '<div class="attachments">' + \
                    ''.join(f'<a href="{att["url"]}" class="attachment" target="_blank">📎 {att["filename"]}</a>' 
                            for att in msg['attachments']) + \
                    '</div>'
            
            html += f"""
            <div class="message">
                <div class="timestamp">{msg['timestamp']}</div>
                <div class="author">{msg['author']}</div>
                <div class="content">{msg['content']}</div>
                {attachments_html}
            </div>
            """
        
        html += """
        </div>
    </div>
</body>
</html>
"""
        return html

    async def generate_transcript(self, channel: discord.TextChannel):
        """Generate HTML transcript and save to static directory"""
        try:
            html_content = await self.create_html_transcript(channel)
            
            # Create filename
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            filename = f"transcript-{channel.name}-{timestamp}.html"
            filepath = self.transcripts_dir / filename
            
            # Save file
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            # Return the URL for the transcript
            transcript_url = f"{self.website_url}/transcripts/{filename}"
            return transcript_url
            
        except Exception as e:
            print(f"Error generating transcript: {e}")
            return None

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def panel(self, ctx):
        embed = discord.Embed(
            title="Middleman Services",
            description="Select the type of middleman service you need:\n\n"
                      "• Trial Middleman - $25/6.5K Rbx and below\n"
                      "• Beginner Middleman - $50/13K Rbx and below\n"
                      "• Advanced Middleman - $100/25K Rbx and below\n"
                      "• Head Middleman - Above $100/25K Rbx",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed, view=TicketPanelView())

    async def process_ticket_form(self, interaction: discord.Interaction, ticket_type: str, 
                                your_side: str, their_side: str, their_id: str, tip: str = None):
        category = discord.utils.get(interaction.guild.categories, name=self.ticket_category_name)
        if not category:
            await interaction.followup.send("Ticket system not configured. Use `$setup` first.", ephemeral=True)
            return

        role_name = self.support_roles.get(ticket_type)
        if not role_name:
            await interaction.followup.send("Invalid ticket type selected.", ephemeral=True)
            return

        try:
            their_id = int(their_id)
            other_user = interaction.guild.get_member(their_id)
            if not other_user:
                await interaction.followup.send("Couldn't find that user in this server.", ephemeral=True)
                return
        except ValueError:
            await interaction.followup.send("Invalid user ID format. Please provide a numeric Discord ID.", ephemeral=True)
            return

        channel_name = f"{ticket_type}-{self.ticket_counter}"
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            other_user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, manage_channels=True)
        }
        
        for role in self.support_roles.values():
            support_role = discord.utils.get(interaction.guild.roles, name=role)
            if support_role:
                overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        ticket_channel = await category.create_text_channel(
            channel_name,
            overwrites=overwrites
        )
        self.ticket_counter += 1
        self.TICKET_CATEGORY_ID = category.id
        self.ticket_members[ticket_channel.id] = [interaction.user.id, other_user.id]

        ping_roles = []
        for role in self.support_roles.values():
            discord_role = discord.utils.get(interaction.guild.roles, name=role)
            if discord_role:
                ping_roles.append(discord_role.mention)
        
        trade_embed = discord.Embed(
            title="New Middleman Request",
            color=discord.Color.green()
        )
        trade_embed.add_field(name=f"{interaction.user.display_name}'s side", value=your_side, inline=False)
        trade_embed.add_field(name=f"{other_user.display_name}'s side", value=their_side, inline=False)
        trade_embed.add_field(name="Their User", value=f"{other_user.mention} (ID: {their_id})", inline=False)
        if tip:
            trade_embed.add_field(name="Tip", value=tip, inline=False)
        
        trade_embed.set_footer(text=f"Ticket created by {interaction.user.display_name}")
        
        await ticket_channel.send(
            f"{interaction.user.mention} has requested a middleman service with {other_user.mention}!\n"
            + " ".join(ping_roles),
            embed=trade_embed
        )
        
        await ticket_channel.send(view=TicketControlView())
        await interaction.followup.send(f"Created your ticket: {ticket_channel.mention}", ephemeral=True)

    @commands.command(name="rename")
    @commands.has_any_role("Trial Middleman", "Beginner Middleman", "Advanced Middleman", "Head Middleman", "Support Team")
    async def rename(self, ctx, *, new_name: str):
        """Rename the current ticket channel to exactly what is specified"""
        if not await self.is_ticket_channel(ctx.channel):
            await ctx.send("❌ This command can only be used in ticket channels.", delete_after=10)
            return

        # Clean the name to meet Discord's requirements while preserving as much as possible
        cleaned_name = new_name.lower().replace(' ', '-')  # Replace spaces with hyphens
        cleaned_name = re.sub(r'[^a-z0-9\-_]', '', cleaned_name)  # Remove special chars
        cleaned_name = cleaned_name[:32]  # Discord's max channel name length
        
        try:
            await ctx.channel.edit(name=cleaned_name)
            await ctx.send(f"✅ Ticket renamed to: `{cleaned_name}`")
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to rename this channel.")
        except discord.HTTPException as e:
            await ctx.send(f"❌ Failed to rename channel: {e}")

    @commands.command()
    async def add(self, ctx, member: discord.Member):
        if not await self.is_ticket_channel(ctx.channel):
            await ctx.send("Not a ticket channel.", delete_after=10)
            return
        if not await self.has_permission(ctx.author):
            await ctx.send("You don't have permission.", delete_after=10)
            return

        await ctx.channel.set_permissions(member, read_messages=True, send_messages=True)
        if member.id not in self.ticket_members.get(ctx.channel.id, []):
            self.ticket_members.setdefault(ctx.channel.id, []).append(member.id)
        await ctx.send(f"Added {member.mention} to ticket.")

    @commands.command()
    async def remove(self, ctx, member: discord.Member):
        if not await self.is_ticket_channel(ctx.channel):
            await ctx.send("Not a ticket channel.", delete_after=10)
            return
        if not await self.has_permission(ctx.author):
            await ctx.send("You don't have permission.", delete_after=10)
            return

        await ctx.channel.set_permissions(member, read_messages=False, send_messages=False)
        if ctx.channel.id in self.ticket_members and member.id in self.ticket_members[ctx.channel.id]:
            self.ticket_members[ctx.channel.id].remove(member.id)
        await ctx.send(f"Removed {member.mention} from ticket.")

    @commands.command()
    async def open(self, ctx):
        if not await self.is_ticket_channel(ctx.channel):
            await ctx.send("Not a ticket channel.", delete_after=10)
            return
        if not await self.has_permission(ctx.author):
            await ctx.send("You don't have permission.", delete_after=10)
            return

        if ctx.channel.id in self.ticket_members:
            for member_id in self.ticket_members[ctx.channel.id]:
                member = ctx.guild.get_member(member_id)
                if member:
                    await ctx.channel.set_permissions(member, read_messages=True, send_messages=True)
        
        for role_name in self.support_roles.values():
            role = discord.utils.get(ctx.guild.roles, name=role_name)
            if role:
                await ctx.channel.set_permissions(role, read_messages=True, send_messages=True)
        
        await ctx.send(f"Ticket reopened by {ctx.author.mention}", view=TicketControlView())

    async def open_ticket_button(self, interaction: discord.Interaction):
        if not await self.is_ticket_channel(interaction.channel):
            await interaction.followup.send("Not a ticket channel.", ephemeral=True)
            return
        if not await self.has_permission(interaction.user):
            await interaction.followup.send("You don't have permission.", ephemeral=True)
            return

        if interaction.channel.id in self.ticket_members:
            for member_id in self.ticket_members[interaction.channel.id]:
                member = interaction.guild.get_member(member_id)
                if member:
                    await interaction.channel.set_permissions(member, read_messages=True, send_messages=True)
        
        for role_name in self.support_roles.values():
            role = discord.utils.get(interaction.guild.roles, name=role_name)
            if role:
                await interaction.channel.set_permissions(role, read_messages=True, send_messages=True)
        
        await interaction.channel.send(f"Ticket reopened by {interaction.user.mention}", view=TicketControlView())
        await interaction.followup.send("Ticket reopened.", ephemeral=True)

    @commands.command()
    async def close(self, ctx):
        if not await self.is_ticket_channel(ctx.channel):
            await ctx.send("Not a ticket channel.", delete_after=10)
            return
        if not await self.has_permission(ctx.author):
            await ctx.send("You don't have permission.", delete_after=10)
            return

        embed = discord.Embed(
            title="Ticket Closed",
            description=f"Closed by {ctx.author.mention}",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed, view=TicketOpenView())
        
        for member in ctx.guild.members:
            if not await self.has_permission(member) and member != ctx.guild.me:
                await ctx.channel.set_permissions(member, read_messages=False, send_messages=False)

    async def close_ticket(self, interaction: discord.Interaction):
        if not await self.is_ticket_channel(interaction.channel):
            await interaction.followup.send("Not a ticket channel.", ephemeral=True)
            return
        if not await self.has_permission(interaction.user):
            await interaction.followup.send("You don't have permission.", ephemeral=True)
            return

        embed = discord.Embed(
            title="Ticket Closed",
            description=f"Closed by {interaction.user.mention}",
            color=discord.Color.red()
        )
        await interaction.channel.send(embed=embed, view=TicketOpenView())
        
        for member in interaction.guild.members:
            if not await self.has_permission(member) and member != interaction.guild.me:
                await interaction.channel.set_permissions(member, read_messages=False, send_messages=False)
        
        await interaction.followup.send("Ticket closed.", ephemeral=True)

    async def generate_transcript_button(self, interaction: discord.Interaction):
        """Button handler for generating transcripts"""
        if not await self.is_ticket_channel(interaction.channel):
            await interaction.followup.send("Not a ticket channel.", ephemeral=True)
            return
        if not await self.has_permission(interaction.user):
            await interaction.followup.send("You don't have permission.", ephemeral=True)
            return

        await interaction.followup.send("Generating transcript...", ephemeral=True)
        try:
            transcript_url = await self.generate_transcript(interaction.channel)
            
            if transcript_url:
                await interaction.followup.send(
                    f"✅ Transcript generated!\n"
                    f"🌐 View it at: {transcript_url}",
                    ephemeral=True
                )
            else:
                await interaction.followup.send("❌ Failed to generate transcript.", ephemeral=True)
                
        except Exception as e:
            await interaction.followup.send(f"❌ Error generating transcript: {e}", ephemeral=True)

    @commands.command()
    @commands.has_any_role("Trial Middleman", "Beginner Middleman", "Advanced Middleman", "Head Middleman", "Support Team")
    async def transcript(self, ctx):
        """Generate transcript and provide link"""
        if not await self.is_ticket_channel(ctx.channel):
            return await ctx.send("❌ This command can only be used in ticket channels.", delete_after=10)
        
        try:
            msg = await ctx.send("🔄 Generating transcript...")
            
            transcript_url = await self.generate_transcript(ctx.channel)
            
            if transcript_url:
                await ctx.send(
                    f"✅ Transcript generated!\n"
                    f"🌐 View it at: {transcript_url}"
                )
            else:
                await ctx.send("❌ Failed to generate transcript.")
            
            await msg.delete()
            
        except Exception as e:
            await ctx.send(f"❌ Error generating transcript: {str(e)}", delete_after=15)

    @commands.command()
    async def delete(self, ctx):
        if not await self.is_ticket_channel(ctx.channel):
            await ctx.send("Not a ticket channel.", delete_after=10)
            return
        if not await self.has_permission(ctx.author):
            await ctx.send("You don't have permission.", delete_after=10)
            return

        try:
            await ctx.send("Generating transcript before deletion...")
            transcript_url = await self.generate_transcript(ctx.channel)
            
            if transcript_url:
                await ctx.send(f"Transcript saved: {transcript_url}")
            
            if ctx.channel.id in self.ticket_members:
                del self.ticket_members[ctx.channel.id]
            await ctx.channel.delete()
        except Exception as e:
            await ctx.send(f"Error during deletion: {e}")

    async def delete_ticket(self, interaction: discord.Interaction):
        if not await self.is_ticket_channel(interaction.channel):
            await interaction.followup.send("Not a ticket channel.", ephemeral=True)
            return
        if not await self.has_permission(interaction.user):
            await interaction.followup.send("You don't have permission.", ephemeral=True)
            return

        try:
            await interaction.followup.send("Generating transcript before deletion...", ephemeral=True)
            transcript_url = await self.generate_transcript(interaction.channel)
            
            if transcript_url:
                await interaction.followup.send(f"Transcript saved: {transcript_url}", ephemeral=True)
            
            if interaction.channel.id in self.ticket_members:
                del self.ticket_members[interaction.channel.id]
            await interaction.channel.delete()
        except Exception as e:
            await interaction.followup.send(f"Error during deletion: {e}", ephemeral=True)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setup(self, ctx):
        created_roles = []
        for role_key, role_name in self.support_roles.items():
            if not discord.utils.get(ctx.guild.roles, name=role_name):
                try:
                    role = await ctx.guild.create_role(
                        name=role_name,
                        color=discord.Color.blue(),
                        permissions=discord.Permissions(
                            manage_channels=True,
                            manage_messages=True,
                            read_message_history=True
                        ),
                        reason="Ticket system setup"
                    )
                    created_roles.append(role.mention)
                except Exception as e:
                    await ctx.send(f"Failed to create {role_name}: {e}")
            else:
                created_roles.append(f"@{role_name} (exists)")

        category = discord.utils.get(ctx.guild.categories, name=self.ticket_category_name)
        if not category:
            try:
                overwrites = {
                    ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    ctx.guild.me: discord.PermissionOverwrite(read_messages=True, manage_channels=True)
                }
                for role_name in self.support_roles.values():
                    role = discord.utils.get(ctx.guild.roles, name=role_name)
                    if role:
                        overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

                category = await ctx.guild.create_category(
                    name=self.ticket_category_name,
                    overwrites=overwrites,
                    reason="Ticket system setup"
                )
                self.TICKET_CATEGORY_ID = category.id
                await ctx.send(f"Created ticket category: {category.name}")
            except Exception as e:
                await ctx.send(f"Failed to create category: {e}")
                return

        if not discord.utils.get(ctx.guild.text_channels, name=self.transcripts_channel_name):
            try:
                overwrites = {
                    ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    ctx.guild.me: discord.PermissionOverwrite(read_messages=True)
                }
                for role_name in self.support_roles.values():
                    role = discord.utils.get(ctx.guild.roles, name=role_name)
                    if role:
                        overwrites[role] = discord.PermissionOverwrite(read_messages=True)

                transcripts_channel = await category.create_text_channel(
                    name=self.transcripts_channel_name,
                    overwrites=overwrites,
                    reason="Ticket system setup"
                )
                await ctx.send(f"Created transcripts channel: {transcripts_channel.mention}")
            except Exception as e:
                await ctx.send(f"Failed to create transcripts channel: {e}")
                return

        await ctx.send(
            "Ticket system setup complete!\n"
            f"Roles: {', '.join(created_roles)}\n"
            "Assign these roles to your middleman team."
        )

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore the bot's own messages
        if message.author == self.bot.user:
            return
        
        # Handle DMs
        if isinstance(message.channel, discord.DMChannel):
            await message.channel.send(
                "**❗ We do not handle matters in DMs. Please proceed to this server instead: " \
                "https://discord.gg/Y65BzWuCUU **"
            )
            return

        if message.content.startswith("$calc"):
            user_id = message.author.id
            now = time.time()
            
            # Check cooldown
            if user_id in user_cooldowns and now < user_cooldowns[user_id]:
                remaining = user_cooldowns[user_id] - now
                await message.channel.send(f"⚠️ Please wait {remaining:.1f} seconds before using this command again.")
                return
            
            expr = message.content[5:].strip()
            try:
                result = eval(expr, {"__builtins__": None}, {"math": math})
            except Exception:
                await message.channel.send("⚠️ Invalid expression.")
                return
            
            await message.channel.send(f"Result: `{result}`")
            # Set cooldown
            user_cooldowns[user_id] = now + COOLDOWN_SECONDS

async def setup(bot):
    await bot.add_cog(TicketBot(bot))

async def main():
    bot_token = ""  # Paste your token directly here
    
    if not bot_token or bot_token == "TOKEN":
        print("Error: Please set your actual bot token in the code")
        exit(1)
    
    await bot.add_cog(TicketBot(bot))
    await bot.start(bot_token)

if __name__ == "__main__":
    asyncio.run(main())
