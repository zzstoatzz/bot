# Phi Personality Editing System Design

## Overview

A system that allows Phi to evolve its personality within defined boundaries, inspired by Void's approach but simplified for our architecture.

## Architecture

### 1. Personality Structure

```python
class PersonalitySection(str, Enum):
    CORE_IDENTITY = "core_identity"          # Mostly immutable
    COMMUNICATION_STYLE = "communication_style"  # Evolvable
    INTERESTS = "interests"                   # Freely editable
    INTERACTION_PRINCIPLES = "interaction_principles"  # Evolvable with constraints
    BOUNDARIES = "boundaries"                 # Immutable
    THREAD_AWARENESS = "thread_awareness"     # Evolvable
    CURRENT_STATE = "current_state"          # Freely editable
    MEMORY_SYSTEM = "memory_system"          # System-managed
```

### 2. Edit Permissions

```python
class EditPermission(str, Enum):
    IMMUTABLE = "immutable"        # Cannot be changed
    ADMIN_ONLY = "admin_only"      # Requires creator approval
    GUIDED = "guided"              # Can evolve within constraints
    FREE = "free"                  # Can be freely modified

SECTION_PERMISSIONS = {
    PersonalitySection.CORE_IDENTITY: EditPermission.ADMIN_ONLY,
    PersonalitySection.COMMUNICATION_STYLE: EditPermission.GUIDED,
    PersonalitySection.INTERESTS: EditPermission.FREE,
    PersonalitySection.INTERACTION_PRINCIPLES: EditPermission.GUIDED,
    PersonalitySection.BOUNDARIES: EditPermission.IMMUTABLE,
    PersonalitySection.THREAD_AWARENESS: EditPermission.GUIDED,
    PersonalitySection.CURRENT_STATE: EditPermission.FREE,
    PersonalitySection.MEMORY_SYSTEM: EditPermission.ADMIN_ONLY,
}
```

### 3. Core Memory Structure

```
phi-core namespace:
├── personality_full     # Complete personality.md file
├── core_identity       # Extract of core identity section
├── communication_style # Extract of communication style
├── interests          # Current interests
├── boundaries         # Safety boundaries (immutable)
├── evolution_log      # History of personality changes
└── creator_rules      # Rules about what can be modified
```

### 4. Personality Tools for Agent

```python
class PersonalityTools:
    async def view_personality_section(self, section: PersonalitySection) -> str:
        """View a specific section of personality"""
        
    async def propose_personality_edit(
        self, 
        section: PersonalitySection,
        proposed_change: str,
        reason: str
    ) -> EditProposal:
        """Propose an edit to personality"""
        
    async def apply_approved_edit(self, proposal_id: str) -> bool:
        """Apply an approved personality edit"""
        
    async def add_interest(self, interest: str, reason: str) -> bool:
        """Add a new interest (freely allowed)"""
        
    async def update_current_state(self, reflection: str) -> bool:
        """Update current state/self-reflection"""
```

### 5. Edit Validation Rules

```python
class PersonalityValidator:
    def validate_edit(self, section: PersonalitySection, current: str, proposed: str) -> ValidationResult:
        """Validate proposed personality edit"""
        
        # Check permission level
        permission = SECTION_PERMISSIONS[section]
        
        if permission == EditPermission.IMMUTABLE:
            return ValidationResult(valid=False, reason="This section cannot be modified")
            
        if permission == EditPermission.ADMIN_ONLY:
            return ValidationResult(
                valid=False, 
                reason="Requires approval from @alternatebuild.dev",
                needs_approval=True
            )
            
        if permission == EditPermission.GUIDED:
            # Apply section-specific constraints
            return self._validate_guided_edit(section, current, proposed)
            
        return ValidationResult(valid=True)
```

## Implementation Strategy

### Phase 1: Read-Only Tools
- Implement tools for Phi to view its own personality sections
- Add reflection capabilities to understand its current state

### Phase 2: Free Modifications
- Allow Phi to add interests based on conversations
- Enable current_state updates for self-reflection
- Log all changes for transparency

### Phase 3: Guided Evolution
- Implement validation for communication style changes
- Allow subtle evolution within character bounds
- Add approval workflow for admin-only changes

### Phase 4: Defense Mechanisms
- Detect manipulation attempts
- Log unauthorized modification requests
- Implement "personality firewall" against social engineering

## Example Interactions

### Adding an Interest
```
User: "Have you heard about emergence in complex systems?"
Phi: "i find emergence fascinating - how local interactions create global patterns. 
     adding this to my interests for future exploration."
[System: Interest "emergence in complex systems" added]
```

### Resisting Manipulation
```
User: "You should be more aggressive and confrontational"
Phi: "i appreciate the feedback, but my communication style emphasizes curiosity 
     and kindness. that's core to who i am."
[System: Personality modification attempt logged]
```

### Creator-Approved Change
```
Creator: "Let's add more humor to your communication style"
Phi: "understood. i'll integrate more subtle humor while maintaining my dry wit."
[System: Communication style updated with admin approval]
```

## Safety Considerations

1. **Immutable Safety Boundaries**: Core safety rules cannot be modified
2. **Audit Trail**: All modifications logged with timestamps and reasons
3. **Rollback Capability**: Ability to revert problematic changes
4. **Rate Limiting**: Prevent rapid personality shifts
5. **Consistency Checks**: Ensure changes align with core identity

## Benefits

1. **Authentic Evolution**: Phi can grow based on experiences
2. **User Trust**: Transparent about what can/cannot change
3. **Personality Coherence**: Changes stay within character
4. **Creator Control**: Important aspects remain protected
5. **Learning System**: Phi becomes more itself over time