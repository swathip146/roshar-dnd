#!/usr/bin/env python3
"""
Generate Herald NPCs for the Shards of Honor campaign
Creates Kalak and Nale as detailed NPC characters in the same format as existing player characters
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

@dataclass
class CharacterStats:
    """Character ability scores"""
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10

def create_kalak_herald_txt() -> str:
    """Create Kalak the Herald character sheet in text format"""
    
    return """CHARACTER: Kalak the Herald

BASIC INFORMATION:
Name: Kalak
Race: Herald
Class: Herald
Level: 20
Background: Herald Mentor
Rulebook: Cosmere 5e (Roshar)

ABILITY SCORES:
Strength: 22 (modifier: +6)
Dexterity: 18 (modifier: +4)
Constitution: 24 (modifier: +7)
Intelligence: 20 (modifier: +5)
Wisdom: 16 (modifier: +3)
Charisma: 19 (modifier: +4)

COMBAT STATISTICS:
Hit Points: 400
Armor Class: 22
Proficiency Bonus: +6

FEATURES AND TRAITS:
- **Immortal:** Cannot die of old age, resurrects after death through the Oathpact
- **Honorblade Bond:** Can use any Surge through Kalak's Honorblade (Windrunner/Stoneward Surges: Adhesion and Gravitation, Cohesion and Tension)
- **Stormlight Infusion:** Automatically draws Stormlight from storms and can hold massive amounts
- **Ancient Knowledge:** Knows the complete history of all Desolations and their patterns
- **Herald Authority:** Commands natural respect and obedience from Knights Radiant and spren
- **Planar Awareness:** Can sense threats to the Physical Realm from Shadesmar and the Spiritual Realm
- **Oathpact Connection:** Mystically linked to the other nine Heralds, can sense their locations and status
- **Divine Resistance:** Resistance to all damage types, immunity to disease and poison
- **Legendary Actions:** Can take 3 legendary actions per turn in combat
- **Lair Actions:** Controls environmental effects in places of power (Urithiru, ancient battlefields)
- **Master Combatant:** Proficiency with all weapons and armor, expertise in military strategy
- **Surgebinding Mastery:** Can teach and enhance the abilities of Knights Radiant
- **Herald's Presence:** Inspires courage in allies and can break enemy morale with a glance

EQUIPMENT:
- Kalak's Honorblade (Legendary weapon, grants Windrunner and Stoneward Surges)
- Ancient Shardplate (Adaptive, changes properties based on need)
- Herald's Cloak (Absorbs and stores Stormlight from any source)
- Perfect Dun Spheres x10 (Never lose their Stormlight)
- Ancient Maps of Roshar (Show hidden locations and Oathgates)
- Oathpact Medallion (Symbol of Herald authority)
- Portable Fabrial Workshop (Can create and repair fabrials)
- Herald's Seal of Authority (Grants access to any location or organization)

COSMERE/ROSHAR ATTRIBUTES:
Identity: Herald
Radiant Order: None (Predates the Orders)
Ideal Level: 5 (Beyond normal Radiant progression)
Investiture Points: 100/100
Spren Bond: Honorblade - Kalak's Honorblade (bonded)
Surges Known: Adhesion, Gravitation, Cohesion, Tension (primary), All others (through Honorblade mastery)
Cantrips Known: Stormlight Healing, Honorblade Summon, Herald Presence, Ancient Knowledge
Invested Arts Known: Mass Healing, Planar Travel, Divine Intervention, Time Dilation, Reality Anchor, Desolation Ward, Herald's Command
Languages: Ancient Alethi, Modern Alethi, Azish, Thaylen, Veden, Herdazian, Dawnchant, Spiritual Realm Communication

PROFICIENCIES:
Tool Proficiencies: Smith's Tools, Mason's Tools, Ancient Engineering, Fabrial Construction, Military Strategy
Armor Proficiencies: All armor types, Shardplate
Weapon Proficiencies: All weapons, Honorblades, Shardblades, Ancient Weapons
Saving Throw Proficiencies: Strength, Constitution, Wisdom, Charisma

SKILLS:
- Athletics (Legendary)
- History (Legendary) 
- Insight (Expert)
- Intimidation (Expert)
- Investigation (Expert)
- Medicine (Expert)
- Perception (Expert)
- Persuasion (Expert)
- Religion (Legendary)
- Survival (Expert)

SPELLS:
- Herald-level Invested Arts focusing on protection, healing, and guidance
- Can cast any Windrunner or Stoneward ability at maximum power
- Divine intervention abilities that can alter fate itself

PERSONALITY:
Personality Traits: Kalak bears the weight of millennia and countless Desolations. He is deeply committed to training new Knights Radiant but struggles with overwhelming guilt over abandoning the Oathpact. Despite his divine nature, he shows genuine care for mortals and their struggles. He speaks with the authority of ages but maintains humility about his past failures. When teaching, he becomes animated and passionate, but in quiet moments, the weight of his experiences shows clearly.

Ideals: Redemption through service and sacrifice. Kalak believes that by properly training the new generation of Knights Radiant, he can atone for the Heralds' abandonment of their sacred duties. He values courage above all else, but tempers it with wisdom earned through countless battles. He believes that every life has value and that the strong must protect the weak, even at great personal cost.

Bonds: Bound to the other Heralds through the Oathpact, though that connection is strained by guilt and millennia of separation. Connected to Honor's legacy and the preservation of Roshar against the forces of Odium. Has formed new bonds with the Knights Radiant he mentors, seeing them as the hope for the future and perhaps his path to redemption. Feels responsible for every person who dies to the Voidbringers.

Flaws: Haunted by millennia of guilt and the memory of countless deaths during the Desolations. The torture he endured between Desolations has left psychological scars that sometimes manifest as moments of paralyzing fear or rage. Can become overwhelmed by the scope of the threat facing Roshar, leading to periods of despair. Sometimes becomes overly protective of new Radiants, potentially limiting their growth through excessive caution born from his fear of losing more people he cares about.

BACKSTORY:
Kalak is one of the ten Heralds, divine champions chosen by Honor to fight against the Voidbringers through the endless cycle of Desolations. As the Herald associated with the Windrunners and Stonewards, he wielded immense power through his Honorblade and led armies of Knights Radiant against the forces of Odium for over four thousand years.

Each Desolation followed the same terrible pattern: the Voidbringers would return, bringing destruction across Roshar. The Heralds would lead the resistance, eventually driving back the enemy at enormous cost. Then the Heralds would travel to Braize (Damnation) where they would be tortured by the Voidbringers until their will broke, triggering the next Desolation. This cycle continued for millennia, with each Herald experiencing unimaginable suffering between wars.

After the Last Desolation, Kalak and eight other Heralds made the fateful decision to abandon the Oathpact, unable to bear the torture that awaited them in Damnation. Only Taln, the Herald of War, remained to face the torture alone. This decision haunts Kalak more than any other moment in his long existence, as it left Roshar vulnerable to the return of the Voidbringers.

For centuries, Kalak wandered Roshar in disguise, watching civilizations rise and fall, always haunted by what he had done. He witnessed the True Desolation that destroyed the Knights Radiant and saw the spren retreat from the world in betrayal and pain. The guilt of these events nearly drove him to madness.

Now, with the Everstorm awakening ancient enemies and new Knights Radiant beginning to emerge, Kalak has emerged from hiding to take on the role of mentor and guide. He seeks to train these new Radiants quickly and effectively, knowing that they represent Roshar's best hope against the coming True Desolation. His vast knowledge of Surgebinding, military strategy, and the nature of their enemies makes him an invaluable ally.

However, Kalak struggles with the balance between sharing his knowledge and not overwhelming the new Radiants with the true scope of what they face. He knows that Odium has had centuries to prepare, that the enemy is stronger than ever, and that this time there may be no Heralds to lead the fight. The weight of this knowledge, combined with his guilt over past failures, makes him both a powerful ally and a deeply troubled mentor.

In the current crisis of the Shards of Honor campaign, Kalak serves as the primary guide for the new Knights Radiant. He provides crucial information about the Voidbringers, their tactics, and the artifacts needed to stop them. However, his own psychological struggles and the magnitude of his guilt mean that the party must sometimes help him as much as he helps them. His character arc involves learning to forgive himself and finding a way to be the leader Roshar needs without being crushed by the weight of his past failures.

CHARACTER BUILD SUMMARY:
This is a level 20 Herald Herald with Herald Mentor background.
Key ability scores: STR 22, DEX 18, CON 24, INT 20, WIS 16, CHA 19.
Combat stats: 400 HP, AC 22, +6 proficiency bonus.
Radiant progression: Beyond normal Ideals, Herald, 100 investiture points.

TAGS FOR INDEXING:
Character, Herald, Herald, Herald Mentor, Herald, Level20, Ideal5, Cosmere 5e (Roshar), NPC, Mentor, Kalak, Windrunner, Stoneward"""

def create_nale_herald_txt() -> str:
    """Create Nale the Herald character sheet in text format"""
    
    return """CHARACTER: Nale the Herald

BASIC INFORMATION:
Name: Nale
Race: Herald
Class: Herald
Level: 20
Background: Conflicted Herald
Rulebook: Cosmere 5e (Roshar)

ABILITY SCORES:
Strength: 18 (modifier: +4)
Dexterity: 24 (modifier: +7)
Constitution: 22 (modifier: +6)
Intelligence: 23 (modifier: +6)
Wisdom: 14 (modifier: +2)
Charisma: 17 (modifier: +3)

COMBAT STATISTICS:
Hit Points: 380
Armor Class: 24
Proficiency Bonus: +6

FEATURES AND TRAITS:
- **Immortal:** Cannot die of old age, resurrects after death through the Oathpact
- **Honorblade Bond:** Wields Nale's Honorblade granting Division and Abrasion Surges with perfect mastery
- **Perfect Justice:** Can sense lawbreakers, their crimes, and the appropriate punishment with supernatural accuracy
- **Divine Authority:** Can compel truth from any being and enforce laws with divine backing
- **Execution Rights:** Can instantly kill those he deems guilty of capital crimes through Division
- **Legal Omniscience:** Knows all laws of every nation on Roshar, past and present
- **Planar Jurisdiction:** His authority extends across all three Realms
- **Herald Resistance:** Immunity to charm, fear, and mind-affecting effects
- **Legendary Actions:** Can take 3 legendary actions per turn in combat
- **Lair Actions:** Controls legal and judicial environments, can manifest courtrooms
- **Skybreaker Command:** Leads the order of Skybreakers who serve as his agents
- **Truth Detection:** Cannot be lied to, can force others to speak truth
- **Precision Strike:** Every attack hits exactly where intended with maximum effect
- **Law Enforcement:** Can bind criminals with unbreakable divine restraints

EQUIPMENT:
- Nale's Honorblade (Legendary weapon, grants Division and Abrasion Surges)
- Judicial Shardplate (Adaptive defense, appears as formal robes or armor as needed)
- Cloak of Office (Enhances authority, grants immunity to deception)
- Perfect Spheres x15 (Stormlight storage that never dims)
- Legal Codex of All Nations (Contains every law ever written)
- Execution Warrant (Blank, can be filled for any criminal)
- Truth Detection Fabrial (Forces honesty in a wide area)
- Herald's Seal of Justice (Symbol of ultimate legal authority)
- Skybreaker Communication Device (Contacts his agents anywhere)
- Binding Chains (Can restrain any criminal, even other Heralds)

COSMERE/ROSHAR ATTRIBUTES:
Identity: Herald
Radiant Order: None (Predates the Orders, but leads Skybreakers)
Ideal Level: 5 (Beyond normal Radiant progression)
Investiture Points: 100/100
Spren Bond: Honorblade - Nale's Honorblade (bonded)
Surges Known: Division, Abrasion (perfect mastery)
Cantrips Known: Perfect Strike, Justice Sense, Law Detection, Herald Authority
Invested Arts Known: Execution, Divine Judgment, Truth Compulsion, Planar Binding, Mass Suggestion, Dominate Person, Disintegration, Time Stop
Languages: Ancient Alethi, Modern Alethi, Azish, Thaylen, Veden, Legal Azish, Judicial Script, Divine Law, Spiritual Realm Communication

PROFICIENCIES:
Tool Proficiencies: Calligrapher's Supplies, Forgery Kit, Legal Documents, Investigation Tools, Judicial Instruments
Armor Proficiencies: All armor types, Judicial Robes
Weapon Proficiencies: All weapons, Honorblades, Precision Weapons, Execution Weapons
Saving Throw Proficiencies: Dexterity, Intelligence, Wisdom, Charisma

SKILLS:
- Deception (Legendary)
- History (Legendary)
- Insight (Legendary)
- Intimidation (Legendary)
- Investigation (Legendary)
- Perception (Expert)
- Persuasion (Expert)
- Religion (Expert)
- Sleight of Hand (Expert)
- Stealth (Expert)

SPELLS:
- Herald-level Invested Arts focusing on justice, truth, and execution
- Can use Division to destroy anything he deems unlawful
- Divine judgment abilities that can determine guilt and assign punishment
- Truth compulsion that works on any being

PERSONALITY:
Personality Traits: Nale is obsessed with law, order, and preventing another Desolation through absolute adherence to legal structures. He is cold, calculating, and absolutely convinced of his righteousness, showing little mercy to those he deems lawbreakers. Every action is measured against legal precedent and the greater good as he sees it. He speaks with precise, formal language and becomes visibly agitated when confronted with legal ambiguity or chaos. However, the current crisis is forcing him to question his methods and beliefs for the first time in millennia.

Ideals: Perfect Justice and the prevention of Desolations through absolute law and order. Nale believes that strict adherence to established legal systems and the elimination of chaos-causing elements (like unsanctioned Knights Radiant) will prevent another catastrophic war. He values order, precision, legal precedent, and the greater good over individual lives, freedoms, or even mercy. Justice, to him, is not about compassion but about perfect application of law.

Bonds: Bound to the concept of Justice itself and the legal systems of every nation on Roshar. Connected to his organization of Skybreakers who serve as his agents and enforcers across the continent. Bound by the Oathpact to the other Heralds, though he views most of them as failures. Increasingly conflicted about his relationship with the law itself as he faces evidence that his interpretation may be flawed.

Flaws: Absolutely obsessed with preventing Desolations to the point of causing great harm to innocents. Unable to see nuance in situations, viewing everything through a rigid legal framework of guilty/innocent, lawful/unlawful. His obsession has made him paranoid and dangerous, willing to kill potential Knights Radiant to prevent what he believes will be another Desolation. Struggles with the realization that his methods may be wrong, which threatens his entire worldview and sense of purpose.

BACKSTORY:
Nale is the Herald of Justice, associated with the Skybreakers and wielding the Surges of Division and Abrasion through his Honorblade. Unlike the other Heralds, Nale never fully abandoned his duties after the Last Desolation. Instead, he became obsessed with preventing another Desolation by eliminating what he believed to be the root cause: Knights Radiant who break their oaths and cause their spren to die.

Nale's interpretation of the cycle was that the return of Knights Radiant inevitably leads to their betrayal and abandonment, which causes massive spiritual damage that triggers the return of the Voidbringers. To prevent this, he has spent centuries leading the Skybreakers in hunting down nascent Knights Radiant, believing that eliminating them before they can grow powerful enough to cause damage would break the cycle.

His methods are ruthless and precise. Using his mastery of law and his divine authority, Nale has created a network of agents who identify potential Radiants and eliminate them before they can speak their second oath. He justifies these killings through legal technicalities and his absolute belief that he is preventing a greater catastrophe.

For over a thousand years, this approach seemed to work. No new Desolation came, and Nale took this as proof that his methods were correct. He became increasingly rigid in his thinking, viewing any deviation from established law as a threat to the stability he had created.

However, the return of the Voidbringers through the Everstorm has shattered Nale's worldview. The evidence that Desolations can occur without Knights Radiant is forcing him to confront the possibility that his centuries of work have been not only wrong but actively harmful to Roshar's defense. This realization is causing a crisis of faith that threatens to destroy his sanity.

In the current crisis of the Shards of Honor campaign, Nale represents a dangerous wild card. His vast knowledge of Surgebinding, his network of Skybreaker agents, and his combat abilities make him potentially valuable as an ally. However, his obsession with law and order, combined with his difficulty accepting that he might be wrong, make him extremely dangerous to work with.

The party must navigate carefully around this Herald. His support could provide crucial advantages - access to the Skybreaker organization, knowledge of legal systems that could provide safe passage, and his combat abilities in the final battle. However, his opposition could be fatal, as he has the power and authority to turn entire nations against the party if he deems them unlawful.

Nale's character arc in the campaign involves his gradual realization that his interpretation of justice has been flawed, and his struggle to find a new purpose in a world where his centuries of work may have made things worse rather than better. Whether he becomes a redeemed ally or a tragic antagonist depends largely on how the party interacts with him and whether they can help him find a new understanding of justice that includes mercy and growth.

CHARACTER BUILD SUMMARY:
This is a level 20 Herald Herald with Conflicted Herald background.
Key ability scores: STR 18, DEX 24, CON 22, INT 23, WIS 14, CHA 17.
Combat stats: 380 HP, AC 24, +6 proficiency bonus.
Radiant progression: Beyond normal Ideals, Herald, 100 investiture points.

TAGS FOR INDEXING:
Character, Herald, Herald, Conflicted Herald, Herald, Level20, Ideal5, Cosmere 5e (Roshar), NPC, Antagonist, Nale, Skybreaker, Division, Abrasion"""

def main():
    """Generate both Herald NPCs and save them"""
    print("=== Generating Herald NPCs for Shards of Honor Campaign ===")

    # Create the output directory
    os.makedirs("data/players", exist_ok=True)

    # Generate Kalak
    print("\n🌟 Creating Kalak the Herald...")
    kalak_content = create_kalak_herald_txt()
    kalak_path = "data/players/kalak_herald.txt"

    with open(kalak_path, 'w', encoding='utf-8') as f:
        f.write(kalak_content)
    print(f"✓ Kalak saved to: {kalak_path}")

    # Generate Nale
    print("\n⚖️ Creating Nale the Herald...")
    nale_content = create_nale_herald_txt()
    nale_path = "data/players/nale_herald.txt"
    
    with open(nale_path, 'w', encoding='utf-8') as f:
        f.write(nale_content)
    print(f"✓ Nale saved to: {nale_path}")
    
    print("\n🎭 Herald NPCs generated successfully!")
    print("\nThese characters are ready to use in your Shards of Honor campaign:")
    print("- Kalak: Mentor Herald, powerful ally and guide for the party")
    print("- Nale: Conflicted Herald, potential ally or dangerous enemy")
    print("\nBoth characters include:")
    print("  • Complete stat blocks appropriate for level 20 Herald NPCs")
    print("  • Detailed personality traits, ideals, bonds, and flaws")
    print("  • Comprehensive backstories tied to Roshar lore")
    print("  • Equipment and abilities suitable for campaign use")
    print("  • Cosmere-specific attributes (Investiture, Surges, etc.)")

if __name__ == "__main__":
    main()

