// title: Demostració de moviment d'un sprite
// duration: 3.0
// fps: 15
// scale: 2

let fantasma = sprites.create(img`
    . . . . . . . . . . . . . . . .
    . . . . . . . . . . . . . . . .
    . . . . . . . . . . . . . . . .
    . . . . . . . . . . . . . . . .
    . . . . . . . 7 7 . . . . . . .
    . . . . . . 7 7 7 7 . . . . . .
    . . . . . 7 7 7 7 7 7 . . . . .
    . . . . 7 7 7 7 7 7 7 7 . . . .
    . . . . 7 7 7 7 7 7 7 7 . . . .
    . . . . . 7 7 7 7 7 7 . . . . .
    . . . . . . 7 7 7 7 . . . . . .
    . . . . . . . 7 7 . . . . . . .
    . . . . . . . . . . . . . . . .
    . . . . . . . . . . . . . . . .
    . . . . . . . . . . . . . . . .
    . . . . . . . . . . . . . . . .
`, SpriteKind.Player)

scene.setBackgroundColor(9) // Blau clar
fantasma.setPosition(80, 60)
fantasma.setBounceOnWall(true)
fantasma.setVelocity(60, 40)
