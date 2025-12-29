#!/usr/bin/env python3
"""
Generate Herald NPCs for the Shards of Honor campaign
Creates Kalak and Nale as detailed NPC characters using the RAG character generator
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from generators.rag_character_generator import CharacterGenerator, CharacterDetails, CharacterStats

def create_kalak_herald() -> CharacterDetails:
    """Create Kalak the Herald as an NPC"""
    
    # Kalak is an ancient Herald - very high level and powerful
    kalak = CharacterDetails()
    
    # Basic Information
    kalak.name = "Kalak"
    kalak.race = "Herald"  # Unique race for Heralds
    kalak.character_class = "Herald"  # Unique class
    kalak.level = 20  # Maximum level for an ancient being
    kalak.background = "Herald Mentor"
    kalak.rulebook = "Cosmere 5e (Roshar)"
    kalak.identity = "Herald"
    
    # Ability Scores - Heralds are superhuman
    kalak.stats = CharacterStats(
        strength=22,      # Superhuman strength
        dexterity=18,     # Excellent agility
        constitution=24,  # Nearly immortal constitution
        intelligence=20,  # Millennia of knowledge
        wisdom=16,        # Somewhat impaired by guilt and trauma
        charisma=19       # Natural leadership, but haunted
    )
    
    # Combat Statistics
    kalak.hit_points = 400  # Extremely durable
    kalak.armor_class = 22  # Honorblade and natural defenses
    kalak.proficiency_bonus = 6  # Level 20
    kalak.speed = 40  # Enhanced movement
    
    # Herald-specific attributes
    kalak.radiant_order = None  # Heralds predate the Orders
    kalak.ideal_level = 5  # Beyond normal Radiant progression
    kalak.investiture_points = {"current": 100, "maximum": 100}  # Massive investiture pool
    kalak.spren = {"type": "Honorblade", "name": "Kalak's Honorblade", "status": "bonded"}
    
    # Surges - Heralds have access to all surges through their Honorblades
    kalak.surges_known = [
        "Adhesion", "Gravitation", "Division", "Abrasion", "Progression",
        "Illumination", "Transformation", "Transportation", "Cohesion", "Tension"
    ]
    
    # Invested Arts - Herald-level abilities
    kalak.cantrips_known = [
        "Stormlight Healing", "Honorblade Summon", "Herald Presence", "Ancient Knowledge"
    ]
    kalak.spells_known = [
        "Mass Healing", "Planar Travel", "Divine Intervention", "Time Dilation",
        "Reality Anchor", "Desolation Ward", "Herald's Command"
    ]
    
    # Languages - Ancient and comprehensive
    kalak.languages = [
        "Ancient Alethi", "Modern Alethi", "Azish", "Thaylen", "Veden", 
        "Herdazian", "Dawnchant", "Spiritual Realm Communication"
    ]
    
    # Proficiencies - Master of all combat arts
    kalak.weapon_proficiencies = [
        "All Simple Weapons", "All Martial Weapons", "Honorblades", 
        "Shardblades", "Ancient Weapons"
    ]
    kalak.armor_proficiencies = [
        "Light Armor", "Medium Armor", "Heavy Armor", "Shardplate"
    ]
    kalak.tool_proficiencies = [
        "Smith's Tools", "Mason's Tools", "Ancient Engineering", 
        "Fabrial Construction", "Military Strategy"
    ]
    kalak.saving_throw_proficiencies = [
        "Strength", "Constitution", "Wisdom", "Charisma"
    ]
    
    # Skills - Millennia of experience
    kalak.skills = [
        "Athletics", "History", "Insight", "Intimidation", "Investigation",
        "Medicine", "Perception", "Persuasion", "Religion", "Survival"
    ]
    
    # Equipment - Herald-level gear
    kalak.equipment = [
        "Kalak's Honorblade (Windrunner/Stoneward Surges)",
        "Ancient Shardplate (Adaptive)",
        "Herald's Cloak (Stormlight Absorption)",
        "Dun Spheres (Perfect Gems) x10",
        "Ancient Maps of Roshar",
        "Oathpact Medallion",
        "Portable Fabrial Workshop",
        "Herald's Seal of Authority"
    ]
    
    # Features - Herald abilities
    kalak.features = [
        "Immortal: Cannot die of old age, resurrects after death",
        "Honorblade Bond: Can use any Surge through the blade",
        "Stormlight Infusion: Automatically draws Stormlight from storms",
        "Ancient Knowledge: Knows the history of all Desolations",
        "Herald Authority: Commands respect from all Radiants",
        "Planar Awareness: Can sense threats to the Physical Realm",
        "Oathpact Connection: Linked to the other Heralds",
        "Divine Resistance: Resistance to all damage types",
        "Legendary Actions: Can take 3 legendary actions per turn",
        "Lair Actions: Controls environmental effects in sacred places"
    ]
    
    # Personality
    kalak.personality_traits = "Kalak bears the weight of millennia and countless Desolations. He is deeply committed to training new Knights Radiant but struggles with guilt over abandoning the Oathpact. Despite his divine nature, he shows genuine care for mortals and their struggles. He speaks with the authority of ages but maintains humility about his past failures."
    
    kalak.ideals = "Redemption through service. Kalak believes that by properly training the new generation of Knights Radiant, he can atone for the Heralds' abandonment of their duties. He values courage, sacrifice, and the protection of the innocent above all else."
    
    kalak.bonds = "Bound to the other Heralds through the Oathpact, though that connection is strained. Connected to Honor's legacy and the preservation of Roshar. Has formed new bonds with the Knights Radiant he mentors, seeing them as the hope for the future."
    
    kalak.flaws = "Haunted by millennia of guilt and the memory of countless deaths during the Desolations. Sometimes becomes overwhelmed by the scope of the threat facing Roshar. Can be overly protective of new Radiants, potentially limiting their growth through excessive caution."
    
    # Backstory
    kalak.backstory = """Kalak is one of the ten Heralds, divine champions who fought against the Voidbringers for millennia through countless Desolations. As the Herald associated with the Windrunners and Stonewards, he wielded immense power through his Honorblade and led armies against the forces of Odium.

After the Last Desolation, Kalak and the other Heralds made the fateful decision to abandon the Oathpact, unable to bear the torture that awaited them in Damnation between Desolations. This decision haunts him deeply, as it left Roshar vulnerable to the return of the Voidbringers.

Now, with the Everstorm awakening ancient enemies and new Knights Radiant beginning to emerge, Kalak has taken on the role of mentor and guide. He seeks to train these new Radiants quickly and effectively, knowing that they represent Roshar's best hope against the coming Desolation. His vast knowledge of Surgebinding, military strategy, and the nature of their enemies makes him an invaluable ally, though his guilt and the weight of his failures sometimes cloud his judgment.

In the current crisis, Kalak serves as both a powerful combatant and a source of crucial information about the Voidbringers, their tactics, and the true nature of the conflict that has shaped Roshar's history."""
    
    return kalak

def create_nale_herald() -> CharacterDetails:
    """Create Nale the Herald as an NPC"""
    
    # Nale is the Herald of Justice - conflicted and dangerous
    nale = CharacterDetails()
    
    # Basic Information
    nale.name = "Nale"
    nale.race = "Herald"  # Unique race for Heralds
    nale.character_class = "Herald"  # Unique class
    nale.level = 20  # Maximum level for an ancient being
    nale.background = "Conflicted Herald"
    nale.rulebook = "Cosmere 5e (Roshar)"
    nale.identity = "Herald"
    
    # Ability Scores - Nale is focused on precision and justice
    nale.stats = CharacterStats(
        strength=18,      # Strong but not his primary focus
        dexterity=24,     # Incredible precision and speed
        constitution=22,  # Herald durability
        intelligence=23,  # Brilliant legal mind and strategist
        wisdom=14,        # Impaired by obsession with preventing Desolations
        charisma=17       # Commanding but cold presence
    )
    
    # Combat Statistics
    nale.hit_points = 380  # Slightly less than Kalak due to different focus
    nale.armor_class = 24  # Superior defensive techniques
    nale.proficiency_bonus = 6  # Level 20
    nale.speed = 50  # Enhanced by Division and Abrasion
    
    # Herald-specific attributes
    nale.radiant_order = None  # Heralds predate the Orders
    nale.ideal_level = 5  # Beyond normal Radiant progression
    nale.investiture_points = {"current": 100, "maximum": 100}  # Massive investiture pool
    nale.spren = {"type": "Honorblade", "name": "Nale's Honorblade", "status": "bonded"}
    
    # Surges - Nale's Honorblade grants Division and Abrasion
    nale.surges_known = [
        "Division", "Abrasion"  # Primary surges from his Honorblade
    ]
    
    # Invested Arts - Herald-level abilities focused on justice and precision
    nale.cantrips_known = [
        "Perfect Strike", "Justice Sense", "Law Detection", "Herald Authority"
    ]
    nale.spells_known = [
        "Execution", "Divine Judgment", "Truth Compulsion", "Planar Binding",
        "Mass Suggestion", "Dominate Person", "Disintegration", "Time Stop"
    ]
    
    # Languages - Legal and administrative focus
    nale.languages = [
        "Ancient Alethi", "Modern Alethi", "Azish", "Thaylen", "Veden",
        "Legal Azish", "Judicial Script", "Divine Law", "Spiritual Realm Communication"
    ]
    
    # Proficiencies - Master of precision combat and law
    nale.weapon_proficiencies = [
        "All Simple Weapons", "All Martial Weapons", "Honorblades",
        "Precision Weapons", "Execution Weapons"
    ]
    nale.armor_proficiencies = [
        "Light Armor", "Medium Armor", "Heavy Armor", "Judicial Robes"
    ]
    nale.tool_proficiencies = [
        "Calligrapher's Supplies", "Forgery Kit", "Legal Documents",
        "Investigation Tools", "Judicial Instruments"
    ]
    nale.saving_throw_proficiencies = [
        "Dexterity", "Intelligence", "Wisdom", "Charisma"
    ]
    
    # Skills - Legal and investigative expertise
    nale.skills = [
        "Deception", "History", "Insight", "Intimidation", "Investigation",
        "Perception", "Persuasion", "Religion", "Sleight of Hand", "Stealth"
    ]
    
    # Equipment - Herald of Justice gear
    nale.equipment = [
        "Nale's Honorblade (Division/Abrasion Surges)",
        "Judicial Shardplate (Adaptive Defense)",
        "Cloak of Office (Authority Enhancement)",
        "Perfect Spheres (Stormlight Storage) x15",
        "Legal Codex of All Nations",
        "Execution Warrant (Blank)",
        "Truth Detection Fabrial",
        "Herald's Seal of Justice"
    ]
    
    # Features - Herald of Justice abilities
    nale.features = [
        "Immortal: Cannot die of old age, resurrects after death",
        "Honorblade Bond: Can use Division and Abrasion Surges",
        "Perfect Justice: Can sense lawbreakers and their crimes",
        "Divine Authority: Can compel truth and enforce laws",
        "Execution Rights: Can instantly kill those he deems guilty",
        "Legal Omniscience: Knows all laws of every nation",
        "Planar Jurisdiction: Authority extends across realms",
        "Herald Resistance: Immunity to charm and fear effects",
        "Legendary Actions: Can take 3 legendary actions per turn",
        "Lair Actions: Controls legal and judicial environments"
    ]
    
    # Personality
    nale.personality_traits = "Nale is obsessed with law, order, and preventing another Desolation. He believes that Knights Radiant cause Desolations and has spent centuries hunting them down. Cold, calculating, and absolutely convinced of his righteousness, he shows little mercy to those he deems lawbreakers. However, the current crisis is forcing him to question his methods and beliefs."
    
    nale.ideals = "Perfect Justice and the prevention of Desolations at any cost. Nale believes that strict adherence to law and the elimination of Knights Radiant will prevent another catastrophic war. He values order, precision, and the greater good over individual lives or freedoms."
    
    nale.bonds = "Bound to the concept of Justice itself and the laws of every nation on Roshar. Connected to his organization of Skybreakers who serve as his agents. Increasingly conflicted about his relationship with the other Heralds and his role in the coming crisis."
    
    nale.flaws = "Absolutely obsessed with preventing Desolations to the point of causing great harm. Unable to see the nuance in situations, viewing everything in terms of legal/illegal, guilty/innocent. His rigid thinking makes him dangerous to allies and enemies alike. Struggles with the realization that his methods may be wrong."
    
    # Backstory
    nale.backstory = """Nale is the Herald of Justice, associated with the Skybreakers and wielding the Surges of Division and Abrasion through his Honorblade. Unlike the other Heralds, Nale never fully abandoned his duties after the Last Desolation. Instead, he became obsessed with preventing another Desolation by eliminating what he believed to be the cause: Knights Radiant.

For centuries, Nale has led the Skybreakers in hunting down nascent Knights Radiant, believing that their return would trigger another catastrophic war. His methods are ruthless and precise, using his mastery of law and his divine authority to justify his actions. He has become a figure of terror among those who show signs of Radiant abilities.

However, the return of the Voidbringers and the Everstorm has begun to shake Nale's convictions. The evidence that Desolations can occur without Knights Radiant is forcing him to confront the possibility that his centuries of work have been not only wrong but actively harmful to Roshar's defense.

In the current crisis, Nale represents a wild card - a powerful ally who could turn enemy at any moment. His vast knowledge of Surgebinding and his network of Skybreaker agents make him valuable, but his obsession with law and order, combined with his difficulty accepting that he might be wrong, make him extremely dangerous to work with. The party must navigate carefully around this Herald, as his support could be crucial, but his opposition could be fatal."""
    
    return nale

def main():
    """Generate both Herald NPCs and save them"""
    print("=== Generating Herald NPCs for Shards of Honor Campaign ===")
    
    # Initialize the generator
    generator = CharacterGenerator(verbose=True)
    generator.set_rulebook("Cosmere 5e (Roshar)")
    
    # Create the Heralds
    print("\n🌟 Creating Kalak the Herald...")
    kalak = create_kalak_herald()
    
    print("\n⚖️ Creating Nale the Herald...")
    nale = create_nale_herald()
    
    # Save characters to appropriate locations
    print("\n💾 Saving characters...")
    
    # Save to docs/players directory to match existing format
    os.makedirs("docs/players", exist_ok=True)
    
    # Export Kalak
    kalak_txt_path = "docs/players/kalak_herald.txt"
    if generator.export_character_to_txt(kalak, kalak_txt_path):
        print(f"✓ Kalak saved to: {kalak_txt_path}")
    else:
        print("❌ Failed to save Kalak")
    
    # Export Nale
    nale_txt_path = "docs/players/nale_herald.txt"
    if generator.export_character_to_txt(nale, nale_txt_path):
        print(f"✓ Nale saved to: {nale_txt_path}")
    else:
        print("❌ Failed to save Nale")
    
    # Also save JSON versions for programmatic use
    kalak_json_path = "docs/players/kalak_herald.json"
    nale_json_path = "docs/players/nale_herald.json"
    
    if generator.save_character(kalak, kalak_json_path):
        print(f"✓ Kalak JSON saved to: {kalak_json_path}")
    
    if generator.save_character(nale, nale_json_path):
        print(f"✓ Nale JSON saved to: {nale_json_path}")
    
    print("\n🎭 Herald NPCs generated successfully!")
    print("\nThese characters are ready to use in your Shards of Honor campaign.")
    print("- Kalak: Mentor Herald, powerful ally and guide")
    print("- Nale: Conflicted Herald, potential ally or dangerous enemy")
    
    return kalak, nale

if __name__ == "__main__":
    main()

