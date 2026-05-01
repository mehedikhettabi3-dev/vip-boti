from PIL import Image, ImageDraw, ImageFont
import os
import json

def create_catalog_image(catalog_data, output_path):
    width = 1080
    height = 1920
    # Rich Gradient Background Effect (Simulation)
    img = Image.new('RGB', (width, height), color='#0a0a1a') 
    draw = ImageDraw.Draw(img)
    
    gold = '#f5c842'
    dark_gold = '#8a6825'
    white = '#ffffff'
    cyan = '#00d4ff'

    # Load Fonts
    try:
        font_title = ImageFont.truetype("arialbd.ttf", 80)
        font_sub   = ImageFont.truetype("arial.ttf", 35)
        font_num   = ImageFont.truetype("courbd.ttf", 55)
        font_tier  = ImageFont.truetype("arialbd.ttf", 45)
    except:
        font_title = font_sub = font_num = font_tier = ImageFont.load_default()

    # Borders
    draw.rectangle([20, 20, width-20, height-20], outline=gold, width=4)
    draw.rectangle([35, 35, width-35, height-35], outline=dark_gold, width=2)

    # Header
    draw.text((width/2, 180), "VIP NUMBERS", fill=gold, font=font_title, anchor="mm")
    draw.text((width/2, 260), "ELITE CATALOGUE - MOROCCO", fill=white, font=font_sub, anchor="mm")
    
    # Render Numbers by Tier
    tiers_to_draw = ['diamond', 'platinum', 'gold']
    tier_labels = {'diamond': "💎 DIAMOND (150 DH)", 'platinum': "🥇 PLATINUM (100 DH)", 'gold': "🥈 GOLD (50 DH)"}
    tier_colors = {'diamond': cyan, 'platinum': '#b482ff', 'gold': '#ffaa33'}

    curr_y = 380
    for tier in tiers_to_draw:
        items = [i for i in catalog_data.get(tier, []) if i.get("status", "available") == "available"]
        if not items: continue

        # Tier Header
        t_color = tier_colors.get(tier, gold)
        draw.text((width/2, curr_y), tier_labels[tier], fill=t_color, font=font_tier, anchor="mm")
        curr_y += 70
        draw.line([(300, curr_y), (width-300, curr_y)], fill=t_color, width=2)
        curr_y += 60

        # Numbers in 2 columns
        for i, item in enumerate(items):
            col = i % 2
            row = i // 2
            x = (width/4 + 50) if col == 0 else (3*width/4 - 50)
            y = curr_y + (row * 100)
            
            # Sub-Background for number
            draw.rectangle([x-210, y-40, x+210, y+40], fill="#111122", outline=t_color, width=1)
            draw.text((x, y-5), item["number"], fill=white, font=font_num, anchor="mm")
            
            if col == 1 or i == len(items)-1:
                if col == 1 or i == len(items)-1:
                    pass # Handled by loop

        # Update y for next tier
        rows = (len(items) + 1) // 2
        curr_y += (rows * 110) + 40
        
        # Stop if too long
        if curr_y > height - 150: break

    # Footer
    draw.text((width/2, height-100), "TÉLÉCHARGEZ VOTRE NUMÉRO SUR WHATSAPP: +212 778 375 026", fill=gold, font=font_sub, anchor="mm")

    img.save(output_path)
    return output_path
