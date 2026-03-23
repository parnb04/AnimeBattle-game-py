

#  Anime Battle: 2D Boss-Rush Platformer

**Anime Battle** is an original 2D action-platformer developed using **Python** and **Pygame**. Players navigate a mysterious ancient chamber to choose between two magical paths, each leading to a unique 1-on-1 boss encounter against legendary icons **Naruto** or **Luffy**.

##  Objective
Enter the chamber, select your opponent, and utilize precise combat mechanics to defeat all enemies and emerge victorious.

##  Key Features
* **Entity System:** Custom-built player and enemy sprite handling.
* **Intelligent AI:** Dynamic behavior patterns where enemies track and engage the player.
* **Immersive Audio:** Integrated background music and spatial sound effects.
* **Fluid UX:** Animated state transitions and a robust state-based game structure.

##  Technical Architecture (OOP)
This project emphasizes **Object-Oriented Programming (OOP)** to manage complex game logic:

### **Character (Base Class)**
The core foundation for all entities, managing:
* **Physics:** Gravity and jumping mechanics.
* **Combat:** Health systems and knockback physics.
* **Collision:** Precise AABB (Axis-Aligned Bounding Box) detection.

### **Player (Inheritance)**
Extends the Character class to include:
* Real-time keyboard input processing.
* Player-specific jump and movement scaling.
* Dynamic sprite rendering.

### **Enemy (Inheritance)**
Extends the Character class with:
* **AI Logic:** Pathfinding to move toward and engage the player.
* Unique identity properties for Naruto and Luffy.

### **Door System**
A dedicated class to manage world transitions, detecting player proximity and triggering specific battle states.

##  System Requirements & Setup
### **Prerequisites**
* **Python:** Version 3.8+ recommended.
* **Pygame:** `pip install pygame`

### **Installation**
Ensure the following directory structure is maintained:
* `main.py`
* `img/` (Visual assets)
* `sound/` (Audio assets)

**To Launch:** `python main.py`

##  Controls
| Action | Hub / Navigation | Battle Mode |
| :--- | :--- | :--- |
| **Move** | Left / Right Arrows | Left / Right Arrows |
| **Jump** | Up Arrow | Up Arrow |
| **Interact / Attack** | Space / Enter | Space |
| **Exit / Return** | — | ESC |
| **Restart** | — | R (on Game Over) |

##  Systems Implemented
* **Physics:** Gravity, jumping, and ground-level collision.
* **Combat:** Attack cooldowns, hit detection, and knockback.
* **State Machine:** Manages logic between **Menu**, **Hub**, **Battle**, and **Game Over**.
* **Audio Engine:** Location-based music triggers and event-driven sound effects.

##  Sources & References
* [Pygame Documentation](https://www.pygame.org/docs/) - Core engine implementation.
* [Game Programming Patterns](https://gameprogrammingpatterns.com/state.html) - State Machine design.
* **Tutorial Support:** Clear Code, Tech With Tim, and KidsCanCode (Physics and Game Loop structures).

---
**Author:** Parsa Nb
*All gameplay logic and architectural structure were independently developed as a Programming 1 Final Project.*

